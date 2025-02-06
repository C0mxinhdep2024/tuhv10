import re
import logging
from pathlib import Path
from ciscoconfparse import CiscoConfParse
import win32com.client

# Định nghĩa các tiêu chuẩn chính sách mật khẩu
DEFAULT_PASSWORD_STANDARDS = {
    'min_length': 8,
    'require_complexity': {
        'uppercase': True,
        'lowercase': True,
        'number': True,
        'special_char': True
    },
    'history_depth': 5,
    'max_age_days': 90,
    'account_lockout': {
        'max_attempts': 5,
        'lockout_duration': 300  # 5 phút
    }
}

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

def analyze_password_policy(config_text, standards=None):
    """
    Phân tích chính sách mật khẩu
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        standards: Tiêu chuẩn tùy chỉnh (optional)
        
    Returns:
        dict: Kết quả phân tích chính sách
    """
    standards = standards or DEFAULT_PASSWORD_STANDARDS
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': True,
        'policy_details': {},
        'issues': [],
        'config_evidence': []
    }

    # Kiểm tra độ dài mật khẩu
    length_policies = parse.find_objects(r'^security password-policy min-length')
    if length_policies:
        for policy in length_policies:
            match = re.search(r'min-length (\d+)', policy.text)
            if match:
                length = int(match.group(1))
                results['policy_details']['min_length'] = length
                results['config_evidence'].append(policy.text)
                
                if length < standards['min_length']:
                    results['compliant'] = False
                    results['issues'].append(
                        f"Độ dài mật khẩu tối thiểu {length} ký tự "
                        f"(yêu cầu: {standards['min_length']})"
                    )

    # Kiểm tra độ phức tạp
    complexity_checks = [
        ('require-alphabetic', 'Yêu cầu ký tự chữ cái'),
        ('require-numeric', 'Yêu cầu ký tự số'),
        ('require-symbols', 'Yêu cầu ký tự đặc biệt')
    ]

    for pattern, description in complexity_checks:
        complexity_policies = parse.find_objects(f'^security password-policy {pattern}')
        if not complexity_policies:
            results['compliant'] = False
            results['issues'].append(f"Không có {description}")

    return results

def check_password_encryption(config_text):
    """Kiểm tra mã hóa mật khẩu trên thiết bị"""
    results = {
        'encrypted': False,
        'issues': [],
        'config_evidence': []
    }

    # Kiểm tra service password-encryption
    if 'service password-encryption' not in config_text:
        results['issues'].append("Chưa bật tính năng mã hóa mật khẩu")

    # Phân tích các dòng username
    username_patterns = [
        r'username\s+\S+\s+password\s+\d+\s+(\S+)',  # Mật khẩu không mã hóa
        r'username\s+\S+\s+secret\s+\d+\s+(\S+)'     # Mật khẩu mã hóa
    ]

    unencrypted_users = []
    encrypted_users = []

    for line in config_text.splitlines():
        for pattern in username_patterns:
            match = re.search(pattern, line)
            if match:
                if 'password' in line:
                    unencrypted_users.append(line)
                elif 'secret' in line:
                    encrypted_users.append(line)
                results['config_evidence'].append(line)

    if unencrypted_users:
        results['issues'].append(
            f"Phát hiện {len(unencrypted_users)} tài khoản sử dụng mật khẩu chưa mã hóa"
        )
    else:
        results['encrypted'] = True
        results['issues'].append("Tất cả mật khẩu đều được mã hóa")

    return results

def update_excel_with_com(config_file, password_results, encryption_results):
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

            # Cập nhật các ô Excel
            if password_results['compliant'] and encryption_results['encrypted']:
                ws.Range("E35").Value = ws.Range("E4").Value
                ws.Range("G35").Value = "Không"
                ws.Range("H35").Value = ws.Range("H7").Value
            else:
                ws.Range("E35").Value = ws.Range("E5").Value
                ws.Range("G35").Value = ("Khuyến nghị:\n"
                                     "1. Cấu hình chính sách mật khẩu:\n"
                                     "   - Độ dài tối thiểu 8 ký tự\n"
                                     "   - Yêu cầu chữ hoa, chữ thường, số và ký tự đặc biệt\n"
                                     "   - Thiết lập thời gian hết hạn\n"
                                     "2. Mã hóa mật khẩu:\n"
                                     "   - Bật service password-encryption\n"
                                     "   - Sử dụng secret thay vì password\n"
                                     "   - Dùng mã hóa mạnh (type 9)")

            # Gộp các vấn đề
            all_issues = password_results['issues'] + encryption_results['issues']
            ws.Range("F35").Value = "\n".join(all_issues) if all_issues else "Chính sách mật khẩu đã tuân thủ"

            # Áp dụng font
            for cell in ["E35", "F35", "G35", "H35"]:
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
    
    log("\n=== Bắt đầu kiểm tra chính sách mật khẩu ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            # Phân tích chính sách mật khẩu
            password_results = analyze_password_policy(config)
            
            # Kiểm tra mã hóa mật khẩu
            encryption_results = check_password_encryption(config)
            
            # Log kết quả phân tích
            log("\nKết quả phân tích:", log_file)
            log("1. Chính sách mật khẩu:", log_file)
            for issue in password_results['issues']:
                log(f"  - {issue}", log_file)
                
            log("\n2. Mã hóa mật khẩu:", log_file)
            for issue in encryption_results['issues']:
                log(f"  - {issue}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, password_results, encryption_results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()