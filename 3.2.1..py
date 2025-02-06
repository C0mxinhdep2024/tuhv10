import re
from pathlib import Path
import win32com.client

def setup_logging():
    """Thiết lập logging cơ bản."""
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    """Ghi log ra file và console."""
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def parse_interfaces(config):
    """Phân tích và kiểm tra các interface từ cấu hình."""
    results = {
        'compliant_ports': set(),
        'non_compliant_ports': set(),
        'applied_features': {}
    }
    
    # Tách các block interface
    interfaces = config.split('\ninterface ')
    interfaces = [block for block in interfaces if block.strip()]
    
    for block in interfaces:
        # Thêm lại từ khóa 'interface' nếu cần
        full_block = block if block.startswith('interface') else 'interface ' + block
        
        # Lấy tên interface
        interface_name = full_block.split('\n')[0].replace('interface', '').strip()
        
        # Kiểm tra nếu là access port
        if 'switchport access vlan' in full_block:
            # Kiểm tra các tính năng bảo mật
            features = []
            if re.search(r'switchport port-security|port-security', full_block):
                features.append('Port Security')
            if re.search(r'ip arp inspection trust|arp inspection trust', full_block):
                features.append('ARP Inspection')
            if re.search(r'dot1x port-control auto', full_block):
                features.append('802.1x')
            if re.search(r'ip source binding|ip verify source', full_block):
                features.append('Static IP-MAC')
                
            if features:
                results['compliant_ports'].add(interface_name)
                results['applied_features'][interface_name] = features
            else:
                results['non_compliant_ports'].add(interface_name)
    
    return results

def get_recommendations():
    """Tạo các khuyến nghị cấu hình."""
    return """Khuyến nghị cấu hình một trong các giải pháp sau:

1. Port Security:
   interface <port_name>
    switchport port-security
    switchport port-security maximum 1
    switchport port-security violation shutdown
    switchport port-security mac-address sticky

2. Dynamic ARP Inspection:
   ip arp inspection vlan <vlan_id>
   interface <port_name>
    ip arp inspection trust

3. 802.1x:
   aaa new-model
   aaa authentication dot1x default group radius
   dot1x system-auth-control
   interface <port_name>
    dot1x port-control auto

4. Static IP-MAC Mapping:
   interface <port_name>
    ip verify source port-security
   ip source binding <mac> vlan <vlan_id> <ip> interface <port_name>"""

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel."""
    try:
        base_name = file_name.split('_')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file = next(excel_dir.glob(f"{base_name}*.xlsx"), None)
        
        if not excel_file:
            return f"Không tìm thấy file Excel cho {base_name}"

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        
        try:
            wb = excel.Workbooks.Open(str(excel_file.absolute()))
            sheet = wb.ActiveSheet

            if not results['compliant_ports'] and not results['non_compliant_ports']:
                sheet.Range("F16").Value = "Không có port access nào trên thiết bị"
                sheet.Range("E16").Value = sheet.Range("E4").Value
                sheet.Range("G16").Value = "Không"
                sheet.Range("H16").Value = sheet.Range("H7").Value
            elif not results['non_compliant_ports']:
                feature_text = ["Các port access đã được cấu hình:"]
                for port, features in sorted(results['applied_features'].items()):
                    feature_text.append(f"- {port}: {', '.join(features)}")
                sheet.Range("F16").Value = "\n".join(feature_text)
                sheet.Range("E16").Value = sheet.Range("E4").Value
                sheet.Range("G16").Value = "Không"
                sheet.Range("H16").Value = sheet.Range("H7").Value
            else:
                status_text = ["Các port access chưa cấu hình bảo mật:"]
                status_text.extend(f"- {port}" for port in sorted(results['non_compliant_ports']))
                
                if results['compliant_ports']:
                    status_text.append("\nCác port đã cấu hình:")
                    for port, features in sorted(results['applied_features'].items()):
                        status_text.append(f"- {port}: {', '.join(features)}")
                
                sheet.Range("F16").Value = "\n".join(status_text)
                sheet.Range("E16").Value = sheet.Range("E5").Value
                sheet.Range("G16").Value = get_recommendations()
                # Không thay đổi H16 khi không tuân thủ

            wb.Save()
            return f"Đã cập nhật file Excel: {excel_file.name}"
            
        finally:
            wb.Close(SaveChanges=True)
            excel.Quit()
            
    except Exception as e:
        return f"Lỗi cập nhật Excel: {str(e)}"

def main():
    """Hàm chính của script."""
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra bảo mật port access ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = parse_interfaces(content)
            
            if not results['compliant_ports'] and not results['non_compliant_ports']:
                log("Không tìm thấy port access", log_file)
            else:
                if results['non_compliant_ports']:
                    log("Các port không tuân thủ:", log_file)
                    for port in sorted(results['non_compliant_ports']):
                        log(f"- {port}", log_file)
                
                if results['compliant_ports']:
                    log("\nCác port đã cấu hình bảo mật:", log_file)
                    for port, features in sorted(results['applied_features'].items()):
                        log(f"- {port}: {', '.join(features)}", log_file)
            
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()