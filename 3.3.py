import re
from pathlib import Path
import win32com.client
import os

# --- Cấu hình logging đơn giản ---
def setup_logging():
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    """Ghi log ra file và console."""
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def get_access_vlans(config):
    """Lấy danh sách các VLAN của port access."""
    access_vlans = set()
    
    # Tìm các interface blocks
    interface_blocks = re.finditer(
        r'interface\s+([^\n]+)(?:\n(?:[^\n]+))*?(?=\ninterface|\n\S|$)', 
        config,
        re.MULTILINE
    )

    for block in interface_blocks:
        interface_text = block.group(0)
        interface_name = block.group(1).strip()

        # Skip non-physical interfaces và subinterfaces
        if ('.' in interface_name or 
            any(skip in interface_name.lower() 
                for skip in ['vlan', 'port-channel', 'loopback', 'tunnel'])):
            continue

        # Kiểm tra access port
        if re.search(r'switchport mode access', interface_text):
            # Tìm VLAN ID
            vlan_match = re.search(r'switchport access vlan (\d+)', interface_text)
            if vlan_match:
                access_vlans.add(vlan_match.group(1))
            else:
                # Nếu không chỉ định VLAN, mặc định là VLAN 1
                access_vlans.add("1")

    return access_vlans

def check_dhcp_snooping(config):
    """Kiểm tra cấu hình DHCP snooping."""
    results = {
        'access_vlans': set(),
        'enabled_vlans': set(),
        'enabled_global': False,
        'verify_mac': False,
        'option82': False,
        'trust_ports': set()
    }

    # Lấy danh sách VLAN của access ports
    results['access_vlans'] = get_access_vlans(config)

    # Kiểm tra global settings
    results['enabled_global'] = bool(re.search(r'^ip dhcp snooping$', config, re.M))
    results['verify_mac'] = bool(re.search(r'ip dhcp snooping verify mac-address', config))
    results['option82'] = bool(re.search(r'ip dhcp snooping information option', config))

    # Tìm các VLAN đã bật DHCP snooping
    for line in config.splitlines():
        vlan_match = re.search(r'ip dhcp snooping vlan ([\d,-]+)', line)
        if vlan_match:
            # Xử lý dải VLAN (ví dụ: 1-10) và VLAN riêng lẻ
            for part in vlan_match.group(1).split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    results['enabled_vlans'].update(str(x) for x in range(start, end + 1))
                else:
                    results['enabled_vlans'].add(part)

    # Tìm trust ports
    interface_pattern = re.compile(r'interface\s+([^\n]+)(?:\n(?:[^\n]+))*?(?=\ninterface|\n\S|$)', re.M)
    for match in interface_pattern.finditer(config):
        interface_text = match.group(0)
        interface_name = match.group(1).strip()

        if re.search(r'ip dhcp snooping trust', interface_text):
            results['trust_ports'].add(interface_name)

    return results

def get_recommendations():
    """Tạo khuyến nghị cấu hình."""
    return """Khuyến nghị cấu hình DHCP snooping:

1. Bật DHCP Snooping global:
   ip dhcp snooping

2. Bật DHCP Snooping trên các VLAN access:
   ip dhcp snooping vlan <vlan_list>

3. Cấu hình verify MAC để tăng tính bảo mật:
   ip dhcp snooping verify mac-address

4. Bật Option 82:
   ip dhcp snooping information option

5. Cấu hình trust port trên uplink và port DHCP server:
   interface <uplink_port>
    ip dhcp snooping trust"""

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel."""
    try:
        # Tìm file Excel tương ứng
        base_name = file_name.split('_')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file = next(excel_dir.glob(f"{base_name}*.xlsx"), None)
        
        if not excel_file:
            return f"Không tìm thấy file Excel cho {base_name}"

        # Khởi tạo Excel
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        
        try:
            wb = excel.Workbooks.Open(str(excel_file.absolute()))
            sheet = wb.ActiveSheet

            # Kiểm tra các điều kiện tuân thủ
            if not results['access_vlans']:
                # Không có VLAN access
                sheet.Range("F19").Value = "Không có VLAN access nào cần kiểm tra"
                sheet.Range("E19").Value = sheet.Range("E4").Value
                sheet.Range("G19").Value = "Không"
                sheet.Range("H19").Value = sheet.Range("H7").Value
            else:
                # Kiểm tra tuân thủ
                missing_vlans = results['access_vlans'] - results['enabled_vlans']
                is_compliant = (results['enabled_global'] and 
                              not missing_vlans and 
                              bool(results['trust_ports']))

                if is_compliant:
                    # Trường hợp tuân thủ
                    status = []
                    if results['enabled_global']:
                        status.append("DHCP Snooping đã được bật globally")
                    if results['enabled_vlans']:
                        status.append(f"Các VLAN đã bật DHCP Snooping: {', '.join(sorted(results['enabled_vlans']))}")
                    if results['verify_mac']:
                        status.append("Đã bật verify MAC")
                    if results['option82']:
                        status.append("Đã bật Option 82")
                    if results['trust_ports']:
                        status.append(f"Các trust port: {', '.join(sorted(results['trust_ports']))}")
                    
                    sheet.Range("F19").Value = "\n".join(status)
                    sheet.Range("E19").Value = sheet.Range("E4").Value
                    sheet.Range("G19").Value = "Không"
                    sheet.Range("H19").Value = sheet.Range("H7").Value
                else:
                    # Trường hợp không tuân thủ
                    status = []
                    if not results['enabled_global']:
                        status.append("DHCP Snooping chưa được bật globally")
                    if missing_vlans:
                        status.append(f"Các VLAN chưa bật DHCP Snooping: {', '.join(sorted(missing_vlans))}")
                    if not results['verify_mac']:
                        status.append("Chưa bật verify MAC")
                    if not results['option82']:
                        status.append("Chưa bật Option 82")
                    if not results['trust_ports']:
                        status.append("Chưa cấu hình trust port")
                    
                    sheet.Range("F19").Value = "\n".join(status)
                    sheet.Range("E19").Value = sheet.Range("E5").Value
                    sheet.Range("G19").Value = get_recommendations()
                    # Không thay đổi H19 khi không tuân thủ

            wb.Save()
            wb.Close()
            return f"Đã cập nhật file Excel: {excel_file.name}"
            
        finally:
            excel.Quit()
            
    except Exception as e:
        return f"Lỗi cập nhật Excel: {str(e)}"

def main():
    """Hàm chính của script."""
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra cấu hình DHCP snooping ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_dhcp_snooping(content)
            
            # Log kết quả phân tích
            if not results['access_vlans']:
                log("Không tìm thấy VLAN access", log_file)
            else:
                log(f"Access VLANs: {', '.join(sorted(results['access_vlans']))}", log_file)
                if results['enabled_global']:
                    log("DHCP Snooping đã được bật globally", log_file)
                
                if results['enabled_vlans']:
                    log(f"VLANs đã bật DHCP Snooping: {', '.join(sorted(results['enabled_vlans']))}", log_file)
                
                missing_vlans = results['access_vlans'] - results['enabled_vlans']
                if missing_vlans:
                    log(f"VLANs chưa bật DHCP Snooping: {', '.join(sorted(missing_vlans))}", log_file)
                
                if results['trust_ports']:
                    log(f"Trust ports: {', '.join(sorted(results['trust_ports']))}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()