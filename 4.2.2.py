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

def analyze_max_prefix_config(config_text):
    """
    Phân tích cấu hình maximum-prefix trên các BGP neighbor
    
    Args:
        config_text (str): Nội dung cấu hình thiết bị
    
    Returns:
        dict: Kết quả phân tích gồm trạng thái BGP, max-prefix và các messages
    """
    results = {
        'bgp_configured': False,
        'has_max_prefix': False,
        'messages': []
    }

    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)
        
        # Phát hiện cấu hình BGP
        bgp_configs = parse.find_objects(r'^router bgp')
        if not bgp_configs:
            results['messages'].append("Không phát hiện cấu hình BGP")
            return results
            
        results['bgp_configured'] = True
        
        for bgp in bgp_configs:
            # Lấy ASN từ cấu hình BGP
            asn = bgp.text.split()[-1]
            neighbors_found = False
            
            # Kiểm tra từng neighbor
            for child in bgp.children:
                # Tìm dòng cấu hình neighbor
                if 'neighbor' not in child.text:
                    continue
                    
                neighbor_match = re.search(r'neighbor (\S+)', child.text)
                if not neighbor_match:
                    continue
                    
                neighbors_found = True
                neighbor = neighbor_match.group(1)
                has_max_prefix = False
                max_prefix_value = None
                
                # Kiểm tra maximum-prefix cho neighbor này
                for subchild in child.all_children:
                    max_prefix_match = re.search(r'neighbor \S+ maximum-prefix (\d+)', subchild.text)
                    if max_prefix_match:
                        has_max_prefix = True
                        max_prefix_value = int(max_prefix_match.group(1))
                        break

                # Đánh giá cấu hình maximum-prefix
                if has_max_prefix:
                    results['has_max_prefix'] = True
                    if max_prefix_value > 1000000:  # Ngưỡng cảnh báo 1 triệu prefix
                        results['messages'].append(
                            f"ASN {asn}: Neighbor {neighbor} - "
                            f"Cảnh báo: maximum-prefix ({max_prefix_value}) quá cao"
                        )
                    else:
                        results['messages'].append(
                            f"ASN {asn}: Neighbor {neighbor} - "
                            f"Đã cấu hình maximum-prefix {max_prefix_value}"
                        )
                else:
                    results['messages'].append(
                        f"ASN {asn}: Neighbor {neighbor} - "
                        f"Chưa cấu hình maximum-prefix"
                    )
            
            # Thông báo nếu không tìm thấy neighbor nào
            if not neighbors_found:
                results['messages'].append(f"ASN {asn}: Không có cấu hình BGP neighbor")

    except Exception as e:
        results['messages'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")
        
    return results

def update_excel_with_com(config_file, results):
    """Cập nhật kết quả vào file Excel sử dụng COM interface"""
    try:
        # Sử dụng đường dẫn như trong 4.1.5
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

            # Cập nhật các ô Excel dựa vào kết quả
            if not results['bgp_configured']:
                ws.Range("E27").Value = ws.Range("E6").Value
                ws.Range("F27").Value = "Không phát hiện cấu hình BGP"
                ws.Range("G27").Value = ws.Range("H7").Value
                ws.Range("H27").Value = ws.Range("H7").Value
            else:
                if results['has_max_prefix']:
                    ws.Range("E27").Value = ws.Range("E4").Value
                    ws.Range("G27").Value = "Không"
                    ws.Range("H27").Value = ws.Range("H7").Value
                else:
                    ws.Range("E27").Value = ws.Range("E5").Value
                    ws.Range("G27").Value = "Khuyến nghị cấu hình maximum-prefix cho các BGP neighbor để giới hạn số lượng prefix nhận quảng bá"

            # Cập nhật chi tiết vào F27
            ws.Range("F27").Value = "\n".join(results['messages'])
            
            # Áp dụng font 
            for cell in ["E27", "F27", "G27", "H27"]:
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
    # Sử dụng đường dẫn như trong 4.1.5
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs") 
    
    log("\n=== Bắt đầu kiểm tra BGP maximum-prefix ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_max_prefix_config(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Có cấu hình BGP: {results['bgp_configured']}", log_file)
            log(f"- Có maximum-prefix: {results['has_max_prefix']}", log_file)
            
            for message in results['messages']:
                log(f"- {message}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()