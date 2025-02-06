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

def identify_gateway_ports(config):
    """Xác định các port kết nối gateway."""
    gateway_ports = set()
    gateway_ips = set()

    # Tìm gateway IPs từ cấu hình
    for line in config.splitlines():
        if 'ip default-gateway' in line:
            ip = line.split()[-1]
            gateway_ips.add(ip)
        elif 'ip route 0.0.0.0 0.0.0.0' in line:
            ip = line.split()[-1]
            if not any(x in ip.lower() for x in ['null', 'reject']):
                gateway_ips.add(ip)

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

        is_gateway = False
        # Kiểm tra description có chứa gateway/router
        if re.search(r'description.*(?:gateway|router|gw|default)', interface_text, re.I):
            is_gateway = True

        # Kiểm tra IP match với gateway IP
        ip_match = re.search(r'ip address (\d+\.\d+\.\d+\.\d+)', interface_text)
        if ip_match and ip_match.group(1) in gateway_ips:
            is_gateway = True

        if is_gateway:
            gateway_ports.add(interface_name)

    return gateway_ports

def check_port_isolation(config):
    """Kiểm tra cấu hình port isolation."""
    results = {
        'access_ports': set(),
        'non_compliant_ports': set(),
        'gateway_ports': set()
    }

    # Xác định gateway ports
    results['gateway_ports'] = identify_gateway_ports(config)

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
        if not re.search(r'switchport mode access|switchport access vlan', interface_text):
            continue

        results['access_ports'].add(interface_name)

        # Không cần kiểm tra gateway ports
        if interface_name in results['gateway_ports']:
            continue

        # Kiểm tra isolation
        is_isolated = any(cmd in interface_text for cmd in [
            'switchport protected',
            'private-vlan isolated',
            'switchport isolated'
        ])

        if not is_isolated:
            results['non_compliant_ports'].add(interface_name)

    return results

def get_recommendations():
    """Tạo khuyến nghị cấu hình."""
    return """Cấu hình port isolation trên các port access (trừ các port gateway):

1. Sử dụng Protected Port:
   interface <port_name>
    switchport protected

2. Hoặc sử dụng Private VLAN:
   vlan <vlan_id>
    private-vlan isolated
   interface <port_name>
    switchport mode private-vlan host
    switchport private-vlan host-association <vlan_id>"""

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

            if not results['access_ports']:
                # Không có port access
                sheet.Range("F18").Value = "Không có port access nào trên thiết bị"
                sheet.Range("E18").Value = sheet.Range("E4").Value
                sheet.Range("G18").Value = "Không"
                sheet.Range("H18").Value = sheet.Range("H7").Value
            elif not results['non_compliant_ports']:
                # Tất cả port tuân thủ
                status = []
                if results['gateway_ports']:
                    status.append(f"Các port gateway (không cần cấu hình isolate): {', '.join(sorted(results['gateway_ports']))}")
                status.append("Tất cả port access khác đã được cấu hình isolation")
                
                sheet.Range("F18").Value = "\n".join(status)
                sheet.Range("E18").Value = sheet.Range("E4").Value
                sheet.Range("G18").Value = "Không"
                sheet.Range("H18").Value = sheet.Range("H7").Value
            else:
                # Có port chưa được cấu hình
                status = []
                if results['gateway_ports']:
                    status.append(f"Các port gateway (không cần cấu hình isolate): {', '.join(sorted(results['gateway_ports']))}")
                status.append(f"Các port chưa được cấu hình isolation: {', '.join(sorted(results['non_compliant_ports']))}")
                
                sheet.Range("F18").Value = "\n".join(status)
                sheet.Range("E18").Value = sheet.Range("E5").Value
                sheet.Range("G18").Value = get_recommendations()
                # Không thay đổi H18 khi không tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra cấu hình port isolation ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_port_isolation(content)
            
            # Log kết quả phân tích
            if not results['access_ports']:
                log("Không tìm thấy port access", log_file)
            else:
                if results['gateway_ports']:
                    log(f"Gateway ports: {', '.join(sorted(results['gateway_ports']))}", log_file)
                    
                if results['non_compliant_ports']:
                    log("Các port chưa cấu hình isolation:", log_file)
                    for port in sorted(results['non_compliant_ports']):
                        log(f"- {port}", log_file)
                else:
                    log("Tất cả port access không phải gateway đã được cấu hình isolation", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()