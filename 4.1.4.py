import re
import logging
from pathlib import Path
from ciscoconfparse import CiscoConfParse
import win32com.client

def setup_logging():
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def check_auth_string_complexity(config_text, min_length=8):
    results = {
        'compliant': True,
        'auth_strings': {},
        'messages': []
    }

    if not config_text:
        results['messages'].append("Không tìm thấy cấu hình")
        return results

    auth_patterns = {
        'key chain': r'key-string\s+(\S+)',
        'snmp community': r'snmp-server community\s+(\S+)',
        'bgp auth': r'neighbor\s+\S+\s+password\s+(\S+)',
        'ospf auth': r'ip ospf authentication-key\s+(\S+)',
        'isis auth': r'isis password\s+(\S+)'
    }

    for line in config_text.splitlines():
        for auth_type, pattern in auth_patterns.items():
            match = re.search(pattern, line)
            if match:
                auth_string = match.group(1)
                is_complex = (
                    len(auth_string) >= min_length and
                    bool(re.search(r'[A-Z]', auth_string)) and
                    bool(re.search(r'[a-z]', auth_string)) and
                    bool(re.search(r'\d', auth_string))
                )
                results['auth_strings'][auth_string] = is_complex
                if not is_complex:
                    results['compliant'] = False

    return results

def get_recommendations(results):
    if not results['compliant']:
        return """Các chuỗi xác thực chưa đáp ứng yêu cầu về độ phức tạp.
Khuyến nghị:
- Sử dụng chuỗi xác thực có độ dài tối thiểu 8 ký tự.
- Bao gồm chữ hoa, chữ thường và số trong chuỗi xác thực.
- Tránh sử dụng từ dễ đoán hoặc thông tin cá nhân.

Ví dụ chuỗi xác thực đạt yêu cầu:
- Str0ngP@ssw0rd!
- C0mpl3xK3y!123
"""
    return ""  

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

            if results['compliant']:
                sheet.Range("F24").Value = "Tất cả chuỗi xác thực đã đáp ứng yêu cầu về độ phức tạp"
                sheet.Range("E24").Value = sheet.Range("E4").Value
                sheet.Range("G24").Value = "Không"
                sheet.Range("H24").Value = sheet.Range("H7").Value
            else:
                weak_strings = [s for s, c in results['auth_strings'].items() if not c]
                sheet.Range("F24").Value = "Các chuỗi xác thực chưa đáp ứng yêu cầu về độ phức tạp:\n" + \
                    "\n".join(f"- {s}" for s in weak_strings)
                sheet.Range("E24").Value = sheet.Range("E5").Value
                sheet.Range("G24").Value = get_recommendations(results)
                # Không thay đổi H24 khi chưa tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra độ phức tạp chuỗi xác thực ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_auth_string_complexity(content)
            
            # Log kết quả phân tích
            log(f"Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Tuân thủ độ phức tạp: {results['compliant']}", log_file)
            log(f"\nThông tin chi tiết:", log_file)
            for auth_string, is_complex in results['auth_strings'].items():
                log(f"- Chuỗi xác thực: {auth_string} - Đạt yêu cầu: {is_complex}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()