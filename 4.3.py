import re
import logging
from pathlib import Path
from ciscoconfparse import CiscoConfParse
import win32com.client
import ipaddress

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

def get_private_networks():
    """Trả về danh sách các dải private IP theo RFC 1918"""
    return [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16')
    ]

def is_public_ip(ip_str, private_networks):
    """
    Kiểm tra IP có phải public không
    
    Args:
        ip_str: Địa chỉ IP cần kiểm tra
        private_networks: Danh sách dải private

    Returns:
        bool: True nếu là public IP
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
        for network in private_networks:
            if ip in network:
                return False
        return True
    except ValueError:
        return False

def analyze_vrf_configuration(config_text):
    """
    Phân tích cấu hình VRF cho lưu lượng OAM
    
    Args:
        config_text: Nội dung cấu hình thiết bị
    
    Returns:
        dict: Kết quả phân tích VRF
    """
    results = {
        'is_l3_device': False,
        'has_public_interface': False,
        'has_oam_vrf': False,
        'messages': []
    }

    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)
        private_networks = get_private_networks()

        # 1. Kiểm tra thiết bị L3
        physical_intfs = parse.find_objects(r'^interface (?!Vlan)')
        if not physical_intfs:
            results['messages'].append("Thiết bị không có interface vật lý, không phải router hoặc L3 switch")
            return results
            
        results['is_l3_device'] = True

        # 2. Tìm interface public
        public_interfaces = []
        all_interfaces = parse.find_objects(r'^interface')
        
        for intf in all_interfaces:
            intf_name = intf.text.split()[1]
            
            if not any('shutdown' in child.text for child in intf.children):
                ip_addresses = []
                
                for child in intf.children:
                    # Primary IP
                    ip_match = re.search(r'ip address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)(?!\s+secondary)', child.text)
                    if ip_match:
                        ip = ip_match.group(1)
                        if is_public_ip(ip, private_networks):
                            results['has_public_interface'] = True
                            ip_addresses.append(ip)
                            
                    # Secondary IPs        
                    ip_secondary_matches = re.finditer(r'ip address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+secondary', child.text)
                    for match in ip_secondary_matches:
                        ip = match.group(1)
                        if is_public_ip(ip, private_networks):
                            results['has_public_interface'] = True
                            ip_addresses.append(ip)

                if ip_addresses:
                    public_interfaces.append({
                        'name': intf_name,
                        'ip': ip_addresses,
                        'vrf': None
                    })

        if not public_interfaces:
            results['messages'].append("Không tìm thấy interface public")
            return results

        # 3. Kiểm tra VRF
        vrfs = parse.find_objects(r'^vrf definition')
        oam_vrfs = []
        
        for vrf in vrfs:
            vrf_name = vrf.text.split()[-1]
            is_oam = False
            
            if any('oam' in child.text.lower() or 'management' in child.text.lower() 
                  for child in vrf.children):
                is_oam = True
            elif any(keyword in vrf_name.lower() 
                    for keyword in ['oam', 'mgmt', 'manage']):
                is_oam = True
                
            if is_oam:
                results['has_oam_vrf'] = True
                oam_vrfs.append(vrf_name)
                results['messages'].append(f"Tìm thấy VRF OAM: {vrf_name}")

        # 4. Kiểm tra interface public trong VRF OAM
        if oam_vrfs:
            for intf in public_interfaces:
                intf_config = parse.find_objects(f'^interface {intf["name"]}')[0]
                for child in intf_config.children:
                    vrf_match = re.search(r'vrf forwarding (\S+)', child.text)
                    if vrf_match:
                        intf['vrf'] = vrf_match.group(1)
                        
                if not intf['vrf']:
                    results['messages'].append(
                        f"Interface {intf['name']} (IP: {', '.join(intf['ip'])}) "
                        f"không được cấu hình trong VRF OAM")
                elif intf['vrf'] not in oam_vrfs:
                    results['messages'].append(
                        f"Interface {intf['name']} (IP: {', '.join(intf['ip'])}) "
                        f"nằm trong VRF {intf['vrf']} thay vì VRF OAM ({', '.join(oam_vrfs)})")

            # 5. Kiểm tra route public trong VRF OAM
            routes = parse.find_objects(r'^ip route')
            for route in routes:
                if 'vrf' not in route.text:
                    results['messages'].append(
                        f"Route không được cấu hình trong VRF: {route.text.strip()}")
                else:
                    vrf_match = re.search(r'ip route vrf (\S+)', route.text)
                    if vrf_match and vrf_match.group(1) not in oam_vrfs:
                        results['messages'].append(
                            f"Route nằm trong VRF {vrf_match.group(1)} "
                            f"thay vì VRF OAM: {route.text.strip()}")
        else:
            results['messages'].append("Chưa tạo VRF riêng cho lưu lượng OAM")

    except Exception as e:
        results['messages'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")

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

            if not results['is_l3_device']:
                ws.Range("E29").Value = ws.Range("E6").Value
                ws.Range("F29").Value = "Thiết bị không phải router hoặc L3 switch"
                ws.Range("G29").Value = ws.Range("H7").Value
                ws.Range("H29").Value = ws.Range("H7").Value
            else:
                if not results['has_public_interface']:
                    ws.Range("E29").Value = ws.Range("E6").Value
                    ws.Range("F29").Value = "Không tìm thấy interface public"
                    ws.Range("G29").Value = ws.Range("H7").Value
                    ws.Range("H29").Value = ws.Range("H7").Value
                else:
                    if results['has_oam_vrf']:
                        ws.Range("E29").Value = ws.Range("E4").Value
                        ws.Range("F29").Value = "\n".join(results['messages'])
                        ws.Range("G29").Value = "Không"
                        ws.Range("H29").Value = ws.Range("H7").Value
                    else:
                        ws.Range("E29").Value = ws.Range("E5").Value
                        ws.Range("F29").Value = "\n".join(results['messages'])
                        ws.Range("G29").Value = ("Khuyến nghị:\n"
                                             "1. Tạo VRF riêng cho lưu lượng OAM\n"
                                             "2. Chuyển các interface public vào VRF OAM\n"
                                             "3. Cấu hình định tuyến public trong VRF OAM")

            # Áp dụng font
            for cell in ["E29", "F29", "G29", "H29"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình VRF ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_vrf_configuration(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Là thiết bị L3: {results['is_l3_device']}", log_file)
            log(f"- Có interface public: {results['has_public_interface']}", log_file)
            log(f"- Có VRF OAM: {results['has_oam_vrf']}", log_file)
            
            for message in results['messages']:
                log(f"- {message}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()