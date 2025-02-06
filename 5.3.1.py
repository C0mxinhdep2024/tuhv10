import re
import logging
from pathlib import Path
import ipaddress
from ciscoconfparse import CiscoConfParse
import win32com.client

def setup_logging():
    """Thiết lập logging với định dạng và file output chuẩn"""
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    """Ghi log ra cả console và file"""
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def is_ip_in_network(ip_addr, network):
    """Kiểm tra IP có thuộc network không"""
    try:
        return ipaddress.ip_address(ip_addr) in ipaddress.ip_network(network)
    except ValueError:
        return False

def analyze_oob_management(config_text, allowed_mgmt_networks=None):
    """
    Phân tích cấu hình quản trị out-of-band
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        allowed_mgmt_networks: Danh sách dải mạng quản trị cho phép (optional)
        
    Returns:
        dict: Kết quả phân tích cấu hình OOB
    """
    allowed_mgmt_networks = allowed_mgmt_networks or []
    results = {
        'compliant': False,
        'issues': [],
        'mgmt_ip': None,
        'current_config': []
    }

    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True)

        # Tìm interface quản trị
        mgmt_interfaces = parse.find_objects(r'^interface (?:mgmt|Management)')
        mgmt_vlans = parse.find_objects(r'^interface [Vv]lan\d+')
        mgmt_vlan_found = False

        # Kiểm tra interface quản trị độc lập
        if mgmt_interfaces:
            results['compliant'] = True
            for intf in mgmt_interfaces:
                results['current_config'].append(intf.text)
                for child in intf.children:
                    results['current_config'].append(f"  {child.text}")
                    ip_match = re.search(r'ip address (\S+)', child.text)
                    if ip_match:
                        results['mgmt_ip'] = ip_match.group(1)

        # Kiểm tra VLAN quản trị
        for vlan in mgmt_vlans:
            if any('manage' in child.text.lower() for child in vlan.children):
                mgmt_vlan_found = True
                results['compliant'] = True
                results['current_config'].append(vlan.text)
                for child in vlan.children:
                    results['current_config'].append(f"  {child.text}")
                    ip_match = re.search(r'ip address (\S+)', child.text)
                    if ip_match:
                        results['mgmt_ip'] = ip_match.group(1)

        # Kiểm tra IP quản trị nằm trong dải cho phép
        if results['mgmt_ip'] and allowed_mgmt_networks:
            in_allowed_network = any(
                is_ip_in_network(results['mgmt_ip'], network)
                for network in allowed_mgmt_networks
            )
            if not in_allowed_network:
                results['compliant'] = False
                results['issues'].append(
                    f"IP quản trị {results['mgmt_ip']} không nằm trong dải mạng quản trị được phép"
                )

        if not (mgmt_interfaces or mgmt_vlan_found):
            results['issues'].append("Không tìm thấy cổng hoặc VLAN quản trị riêng")

    except Exception as e:
        results['issues'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")

    return results

def update_excel_with_com(config_file, results):
    """Cập nhật kết quả vào file Excel sử dụng COM interface"""
    try:
        base_name = config_file.name.split('_')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file = next(excel_dir.glob(f"{base_name}*.xlsx"), None)
        
        if not excel_file:
            return f"Không tìm thấy file Excel cho {base_name}"

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        
        try:
            wb = excel.Workbooks.Open(str(excel_file.absolute()))
            ws = wb.ActiveSheet

            if results['compliant']:
                ws.Range("E37").Value = ws.Range("E4").Value
                ws.Range("F37").Value = "\n".join(results['current_config'])
                ws.Range("G37").Value = "Không"
                ws.Range("H37").Value = ws.Range("H7").Value
            else:
                ws.Range("E37").Value = ws.Range("E5").Value
                ws.Range("F37").Value = "\n".join(results['issues'])
                if results['issues']:
                    ws.Range("G37").Value = ("Khuyến nghị cấu hình:\n"
                                         "1. Tạo interface hoặc VLAN quản trị riêng\n"
                                         "2. Cấu hình IP thuộc dải mạng quản trị\n"
                                         "3. Áp dụng chính sách bảo mật phù hợp")

            # Áp dụng font
            for cell in ["E37", "F37", "G37", "H37"]:
                ws.Range(cell).Font.Name = "Times New Roman"
                ws.Range(cell).Font.Size = 14

            wb.Save()
            return f"Đã cập nhật file Excel: {excel_file.name}"
            
        finally:
            wb.Close()
            excel.Quit()

    except Exception as e:
        return f"Lỗi cập nhật Excel: {str(e)}"

def main():
    """Hàm chính của script"""
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    # Dải mạng quản trị cho phép
    allowed_networks = ["192.168.1.0/24"]
    
    log("\n=== Bắt đầu kiểm tra cấu hình quản trị out-of-band ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_oob_management(config, allowed_networks)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            if results['mgmt_ip']:
                log(f"- IP quản trị: {results['mgmt_ip']}", log_file)
            
            if results['issues']:
                log("\n- Các vấn đề phát hiện:", log_file)
                for issue in results['issues']:
                    log(f"  - {issue}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình hiện tại:", log_file)
                for line in results['current_config']:
                    log(f"  {line}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()