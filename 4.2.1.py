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

def get_bogon_networks():
    """Trả về danh sách các dải bogon IPv4 và IPv6"""
    bogons_v4 = [
        '0.0.0.0/8',          # RFC 1700
        '10.0.0.0/8',         # RFC 1918
        '100.64.0.0/10',      # RFC 6598 (Shared Address Space)
        '127.0.0.0/8',        # RFC 1122 (Loopback)
        '169.254.0.0/16',     # RFC 3927 (Link Local)
        '172.16.0.0/12',      # RFC 1918 
        '192.0.0.0/24',       # RFC 6890
        '192.0.2.0/24',       # RFC 5737 (TEST-NET-1)
        '192.88.99.0/24',     # RFC 7526 (6to4 Relay)
        '192.168.0.0/16',     # RFC 1918
        '198.18.0.0/15',      # RFC 2544 (Network Interconnect Device Benchmark Testing)
        '198.51.100.0/24',    # RFC 5737 (TEST-NET-2)
        '203.0.113.0/24',     # RFC 5737 (TEST-NET-3)
        '224.0.0.0/4',        # RFC 5771 (Multicast)
        '240.0.0.0/4'         # RFC 1112 (Reserved)
    ]
    
    bogons_v6 = [
        '::/8',               # RFC 4291 (Reserved)
        '100::/64',           # RFC 6666 (Discard-Only Address Block)
        '2001:2::/48',        # RFC 5180 (Benchmarking)
        '2001:10::/28',       # RFC 4843 (ORCHID)
        '2001:db8::/32',      # RFC 3849 (Documentation)
        'fc00::/7',           # RFC 4193 (Unique Local Unicast)
        'fe80::/10',          # RFC 4291 (Link Local Unicast)
        'fec0::/10',          # RFC 3879 (Site Local) - Deprecated
        'ff00::/8'            # RFC 4291 (Multicast)
    ]
    
    return bogons_v4, bogons_v6

def get_martian_networks():
    """Trả về danh sách các dải martian IPv4 và IPv6"""
    martians_v4 = [
        '0.0.0.0/8',          # Source networks
        '127.0.0.0/8',        # Loopback
        '191.255.0.0/16',     # RFC 3330
        '192.0.0.0/24',       # RFC 5736
        '223.255.255.0/24',   # RFC 3330
        '240.0.0.0/4'         # RFC 1112 - Reserved
    ]
    
    martians_v6 = [
        '::/128',             # Unspecified address
        '::1/128',            # Loopback
        'ff00::/8'            # Multicast
    ]
    
    return martians_v4, martians_v6

def is_prefix_in_networks(prefix, networks):
    """Kiểm tra prefix có thuộc dải networks không"""
    try:
        prefix_net = ipaddress.ip_network(prefix, strict=False)
        for network in networks:
            network_net = ipaddress.ip_network(network)
            if prefix_net.overlaps(network_net):
                return True
        return False
    except ValueError:
        return False

def check_prefix_length(prefix):
    """Kiểm tra độ dài prefix có phù hợp không"""
    try:
        network = ipaddress.ip_network(prefix, strict=False)
        if isinstance(network, ipaddress.IPv4Network):
            return network.prefixlen >= 24
        else:
            return network.prefixlen >= 48
    except ValueError:
        return True  # Return True if cannot parse to avoid false positives

def analyze_bgp_prefix_filters(config_text):
    """Phân tích cấu hình BGP prefix filter"""
    results = {
        'bgp_configured': False,
        'has_prefix_filter': False,
        'messages': []
    }
    
    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)
        
        # Kiểm tra cấu hình BGP
        bgp_config = parse.find_objects(r'^router bgp')
        if not bgp_config:
            results['messages'].append("Không phát hiện cấu hình BGP")
            return results
            
        results['bgp_configured'] = True
        
        # Kiểm tra prefix list và route-map
        prefix_lists = parse.find_objects(r'^ip prefix-list')
        route_maps = parse.find_objects(r'^route-map.*permit|deny')
        
        if not prefix_lists and not route_maps:
            results['messages'].append("Chưa cấu hình prefix filter cho BGP")
            return results
            
        results['has_prefix_filter'] = True
        
        # Lấy danh sách bogon và martian networks
        bogons_v4, bogons_v6 = get_bogon_networks()
        martians_v4, martians_v6 = get_martian_networks()
        
        # Phân tích các prefix list
        for plist in prefix_lists:
            match = re.search(r'ip prefix-list (\S+) (permit|deny) ([^le|ge]+)(?:\s+(?:le|ge)\s+\d+)?(?:\s+(?:le|ge)\s+\d+)?', plist.text)
            if match:
                action = match.group(2)
                prefix = match.group(3).strip()
                
                # Kiểm tra độ dài prefix
                if not check_prefix_length(prefix):
                    results['messages'].append(f"Cảnh báo: Prefix {prefix} có độ dài không phù hợp (yêu cầu IPv4 >= /24, IPv6 >= /48)")
                
                # Kiểm tra bogon
                if is_prefix_in_networks(prefix, bogons_v4 + bogons_v6):
                    if action == 'deny':
                        results['messages'].append(f"Đã cấu hình chặn bogon prefix: {prefix}")
                    else:
                        results['messages'].append(f"Cảnh báo: Cho phép bogon prefix: {prefix}")
                
                # Kiểm tra martian
                if is_prefix_in_networks(prefix, martians_v4 + martians_v6):
                    if action == 'deny':
                        results['messages'].append(f"Đã cấu hình chặn martian prefix: {prefix}")
                    else:
                        results['messages'].append(f"Cảnh báo: Cho phép martian prefix: {prefix}")

        # Phân tích route-map và match với prefix-list
        for rmap in route_maps:
            for child in rmap.children:
                if 'match ip address prefix-list' in child.text:
                    prefix_list_name = child.text.split()[-1]
                    results['messages'].append(f"Đã áp dụng prefix filter '{prefix_list_name}' qua route-map: {rmap.text.strip()}")

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
                ws.Range("E26").Value = ws.Range("E6").Value
                ws.Range("F26").Value = "Không phát hiện cấu hình BGP"
                ws.Range("G26").Value = ws.Range("H7").Value
                ws.Range("H26").Value = ws.Range("H7").Value
            else:
                if results['has_prefix_filter']:
                    ws.Range("E26").Value = ws.Range("E4").Value
                    ws.Range("F26").Value = "\n".join(results['messages'])
                    ws.Range("G26").Value = "Không"
                    ws.Range("H26").Value = ws.Range("H7").Value
                else:
                    ws.Range("E26").Value = ws.Range("E5").Value
                    ws.Range("F26").Value = "\n".join(results['messages'])
                    ws.Range("G26").Value = ("Khuyến nghị cấu hình prefix filter để kiểm soát các prefix BGP:\n"
                                         "- Chặn các dải private IP (RFC 1918)\n"
                                         "- Chặn các dải đặc biệt (link-local, multicast, reserved)\n"
                                         "- Chặn các prefix IPv4 < /24, IPv6 < /48\n"
                                         "- Chặn các bogon và martian prefixes")

            # Áp dụng font 
            for cell in ["E26", "F26", "G26", "H26"]:
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
    
    log("\n=== Bắt đầu kiểm tra BGP prefix filter ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_bgp_prefix_filters(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Có cấu hình BGP: {results['bgp_configured']}", log_file)
            log(f"- Có prefix filter: {results['has_prefix_filter']}", log_file)
            
            for message in results['messages']:
                log(f"- {message}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()