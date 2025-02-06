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

def analyze_non_admin_accounts(config_text, admin_role_keywords=None):
    """
    Kiểm tra và phân loại các tài khoản không phải admin
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        admin_role_keywords: Từ khóa xác định vai trò admin (optional)
        
    Returns:
        dict: Kết quả phân tích tài khoản
    """
    if admin_role_keywords is None:
        admin_role_keywords = {"admin", "administrator", "root", "superuser"}
        
    results = {
        'all_accounts': [],
        'admin_accounts': [],
        'non_admin_accounts': [],
        'current_config': []
    }

    try:
        parse = CiscoConfParse(config_text.splitlines(), factory=True)
        
        # Thu thập thông tin cấu hình tài khoản
        user_sections = parse.find_objects(r"^username\s+\S+")
        for user in user_sections:
            match = re.search(r'^username\s+(\S+)', user.text)
            if match:
                username = match.group(1)
                print(username)
                # Kiểm tra username có phải admin không
                is_admin = any(keyword.lower() in username.lower() for keyword in admin_role_keywords)
                print(is_admin)
                account_info = {
                    'username': username,
                    'is_admin': is_admin
                }
                
                results['all_accounts'].append(account_info)
                results['current_config'].append(user.text)

                if is_admin:
                    results['admin_accounts'].append(account_info)
                else:
                    results['non_admin_accounts'].append(account_info)

    except Exception as e:
        results['current_config'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")
        
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

            if len(results['non_admin_accounts']) > 0:  # Pass - có ít nhất 1 tài khoản non-admin
                non_admin_usernames = [account['username'] for account in results['non_admin_accounts']]
                
                ws.Range("E33").Value = ws.Range("E4").Value
                ws.Range("F33").Value = "QTV đã được cấp tài khoản riêng:\n" + "\n".join(
                    f"username {username}" for username in non_admin_usernames
                )
                ws.Range("G33").Value = "Không"
                ws.Range("H33").Value = ws.Range("H7").Value
            else:  # Fail - tất cả đều là tài khoản admin
                ws.Range("E33").Value = ws.Range("E5").Value
                ws.Range("F33").Value = "\n".join(results['current_config'])
                ws.Range("G33").Value = ("Khuyến nghị:\n"
                                     "- Tạo thêm các tài khoản cho QTV với mức privilege thấp hơn 15\n"
                                     "- Hạn chế số lượng tài khoản có quyền admin (privilege 15)\n"
                                     "- Phân quyền rõ ràng cho từng nhóm người dùng")

            # Áp dụng font
            for cell in ["E33", "F33", "G33", "H33"]:
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
    
    log("\n=== Bắt đầu kiểm tra tài khoản non-admin ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_non_admin_accounts(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Tổng số tài khoản: {len(results['all_accounts'])}", log_file)
            log(f"- Số tài khoản admin: {len(results['admin_accounts'])}", log_file)
            log(f"- Số tài khoản non-admin: {len(results['non_admin_accounts'])}", log_file)
            
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