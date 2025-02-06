import re
import logging
from pathlib import Path
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

def analyze_ebgp_filter_port179(config_text):
    """
    Phân tích cấu hình filter TCP port 179 trên các interface eBGP
    
    Args:
        config_text (str): Nội dung cấu hình thiết bị
    
    Returns:
        dict: Kết quả phân tích bao gồm trạng thái BGP, filter và messages
    """
    results = {
        "bgp_configured": False,
        "has_filter": False,
        "messages": []
    }

    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)
        
        # Kiểm tra cấu hình BGP
        bgp_peers = {}
        bgp_configs = parse.find_objects(r'^router bgp \d+')
        
        if not bgp_configs:
            results['messages'].append("Không phát hiện cấu hình BGP")
            return results
            
        results['bgp_configured'] = True
        
        # Thu thập thông tin các eBGP peer
        for bgp in bgp_configs:
            local_asn = re.search(r'router bgp (\d+)', bgp.text).group(1)
            neighbor_lines = [c for c in bgp.children if 'neighbor' in c.text]
            
            for line in neighbor_lines:
                # Tìm neighbor IP và remote AS
                peer_match = re.search(r'neighbor (\S+).*remote-as (\d+)', line.text)
                if peer_match:
                    peer_ip = peer_match.group(1)
                    remote_as = peer_match.group(2)
                    
                    # Chỉ quan tâm eBGP peers (khác AS)
                    if remote_as != local_asn:
                        bgp_peers[peer_ip] = remote_as

        if not bgp_peers:
            results['messages'].append("Không phát hiện cấu hình eBGP peer")
            return results

        # Kiểm tra ACL filter port 179
        has_port_filter = False
        acl_configs = parse.find_objects(r'^ip access-list')
        
        for acl in acl_configs:
            # Tìm các rule filter port 179
            for line in acl.children:
                for peer_ip in bgp_peers:
                    if peer_ip in line.text and '179' in line.text:
                        has_port_filter = True
                        results['messages'].append(
                            f"Đã cấu hình filter port 179 cho peer {peer_ip} (AS{bgp_peers[peer_ip]}): "
                            f"{line.text.strip()}")
                        break

        # Thu thập các interface có cấu hình ACL
        interfaces = parse.find_objects(r'^interface')
        interfaces_with_acl = []
        
        for intf in interfaces:
            # Kiểm tra interface có ACL inbound
            for line in intf.children:
                if 'ip access-group' in line.text and 'in' in line.text:
                    interfaces_with_acl.append(intf.text.split()[1])

        if has_port_filter:
            results['has_filter'] = True
            if interfaces_with_acl:
                results['messages'].append(
                    f"ACL đã được áp dụng trên các interface: {', '.join(interfaces_with_acl)}")
        else:
            results['messages'].append("Chưa cấu hình filter TCP port 179")

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

            if not results['bgp_configured']:
                ws.Range("E28").Value = ws.Range("E6").Value
                ws.Range("F28").Value = "Không phát hiện cấu hình BGP"
                ws.Range("G28").Value = ws.Range("H7").Value
                ws.Range("H28").Value = ws.Range("H7").Value
            else:
                if results['has_filter']:
                    ws.Range("E28").Value = ws.Range("E4").Value
                    ws.Range("F28").Value = "\n".join(results['messages'])
                    ws.Range("G28").Value = "Không"
                    ws.Range("H28").Value = ws.Range("H7").Value
                else:
                    ws.Range("E28").Value = ws.Range("E5").Value
                    ws.Range("F28").Value = "\n".join(results['messages'])
                    ws.Range("G28").Value = "Khuyến nghị cấu hình ACL để filter TCP port 179 cho các eBGP peer"

            # Áp dụng font
            for cell in ["E28", "F28", "G28", "H28"]:
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
    
    log("\n=== Bắt đầu kiểm tra BGP filter port 179 ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_ebgp_filter_port179(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Có cấu hình BGP: {results['bgp_configured']}", log_file)
            log(f"- Có filter port 179: {results['has_filter']}", log_file)
            
            for message in results['messages']:
                log(f"- {message}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()