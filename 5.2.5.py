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

def analyze_login_block_policy(config_text):
    """
    Kiểm tra chính sách khóa tài khoản sau đăng nhập sai
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích chính sách khóa tài khoản
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': False,
        'issues': [],
        'current_config': []
    }

    # Định nghĩa các policy cần kiểm tra
    lock_policies = [
        {
            'pattern': r'^security authentication failure rate (\d+) log',
            'description': 'khóa tài khoản sau <= 5 lần đăng nhập sai trong 5 phút', 
            'check': lambda x: int(x) <= 5
        },
        {
            'pattern': r'^security passwords lock-out (?:.+) (\d+)',
            'description': 'thời gian khóa >= 5 phút',
            'check': lambda x: int(x) >= 300 
        },
        {  
            'pattern': r'^security passwords delay (\d+)',
            'description': 'độ trễ trước khi cho phép thử lại >= 5 giây',
            'check': lambda x: int(x) >= 5
        }
    ]

    for policy in lock_policies:
        matches = parse.find_objects(policy['pattern'])
        if matches:
            results['current_config'].extend(matches)
            if not all(policy['check'](m.split()[-1]) for m in matches):
                results['issues'].append(f"{policy['description']} chưa đạt")
        else:
            results['issues'].append(f"Thiếu cấu hình {policy['description']}")

    if not results['issues']:
        results['compliant'] = True

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
                config_text = "\n".join([f"! {cmd}" for cmd in results['current_config']])
                ws.Range("E36").Value = ws.Range("E4").Value
                ws.Range("F36").Value = config_text
                ws.Range("G36").Value = "Không"
                ws.Range("H36").Value = ws.Range("H7").Value
            else:
                ws.Range("E36").Value = ws.Range("E5").Value
                ws.Range("F36").Value = "Thiết bị không có cấu hình khóa tài khoản"
                ws.Range("G36").Value = ("! Cấu hình khóa tài khoản sau khi đăng nhập sai:\n"
                                     "security authentication failure rate 5 log\n"
                                     "security passwords lock-out interval 900 attempts 5 within 5\n"
                                     "security passwords delay 5")

            # Áp dụng font
            for cell in ["E36", "F36", "G36", "H36"]:
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
    
    log("\n=== Bắt đầu kiểm tra chính sách khóa tài khoản ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_login_block_policy(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            
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