import re
import logging
from pathlib import Path
from ciscoconfparse import CiscoConfParse
import win32com.client

# Constants
MAX_TIMEOUT_MINUTES = 15  # Thời gian timeout tối đa cho phép

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

def parse_timeout_value(timeout_config):
    """
    Chuyển đổi cấu hình timeout thành số phút
    
    Args:
        timeout_config: Chuỗi cấu hình timeout (vd: 'exec-timeout 10 30')
        
    Returns:
        int: Tổng số phút của timeout
    """
    match = re.search(r'exec-timeout (\d+)(?: (\d+))?', timeout_config)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2)) if match.group(2) else 0
        return minutes + (seconds / 60)
    return 0

def analyze_session_timeout(config_text):
    """
    Phân tích cấu hình timeout của các phiên kết nối
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích timeout
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': True,
        'issues': [],
        'current_config': set(),
        'timeout_configs': {}
    }

    try:
        # Kiểm tra timeout trên các line VTY
        vty_lines = parse.find_objects(r'^line vty')
        
        for line in vty_lines:
            line_range = line.text.replace('line vty ', '')
            timeout_value = None
            
            # Tìm cấu hình exec-timeout
            for child in line.children:
                if 'exec-timeout' in child.text:
                    timeout_value = parse_timeout_value(child.text)
                    results['timeout_configs'][line_range] = child.text.strip()
                    
                    # Kiểm tra giá trị timeout
                    if timeout_value > MAX_TIMEOUT_MINUTES:
                        results['compliant'] = False
                        results['issues'].append(
                            f"VTY {line_range}: Timeout ({timeout_value} phút) "
                            f"vượt quá giới hạn cho phép ({MAX_TIMEOUT_MINUTES} phút)"
                        )
                    break
            
            # Nếu không có cấu hình timeout
            if timeout_value is None:
                results['compliant'] = False
                results['issues'].append(f"VTY {line_range}: Chưa cấu hình exec-timeout")

        # Thu thập cấu hình hiện tại
        for line_range, config in results['timeout_configs'].items():
            results['current_config'].add(f"line vty {line_range}\n {config}")

    except Exception as e:
        results['issues'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")
        results['compliant'] = False

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
                ws.Range("E40").Value = ws.Range("E4").Value
                ws.Range("F40").Value = "\n".join(results['current_config'])
                ws.Range("G40").Value = "Không"
                ws.Range("H40").Value = ws.Range("H7").Value
            else:
                ws.Range("E40").Value = ws.Range("E5").Value
                ws.Range("F40").Value = "\n".join(results['issues'])
                ws.Range("G40").Value = (f"Khuyến nghị cấu hình exec-timeout ≤ {MAX_TIMEOUT_MINUTES} "
                                     f"phút cho tất cả các line VTY\n\nVí dụ:\n"
                                     f"line vty 0 4\n exec-timeout {MAX_TIMEOUT_MINUTES} 0")

            # Áp dụng font
            for cell in ["E40", "F40", "G40", "H40"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình session timeout ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_session_timeout(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình hiện tại:", log_file)
                for config in sorted(results['current_config']):
                    log(f"  {config}", log_file)
            
            if results['issues']:
                log("\n- Các vấn đề phát hiện:", log_file)
                for issue in results['issues']:
                    log(f"  - {issue}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()