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

def clean_config_output(config_text):
    """
    Làm sạch dữ liệu đầu ra từ thiết bị
    
    Args:
        config_text (str): Nội dung cấu hình gốc
        
    Returns:
        str: Nội dung cấu hình đã làm sạch
    """
    lines = config_text.splitlines()
    cleaned_lines = []
    seen_lines = set()
    
    for line in lines:
        if not line.strip() or line.strip() in ['!', '#']:
            continue
        if any(line.startswith(prefix) for prefix in ['CORE-IDC', 'show']):
            continue
        if line.strip() not in seen_lines:
            cleaned_lines.append(line.strip())
            seen_lines.add(line.strip())
    
    return '\n'.join(cleaned_lines)

def analyze_aaa_config(config_text):
    """
    Phân tích cấu hình AAA và tài khoản local
    
    Args:
        config_text (str): Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích AAA và tài khoản
    """
    config_text = clean_config_output(config_text)
    
    usernames = set()
    current_config = []
    aaa_status = "no aaa new-model" in config_text.lower()
    
    for line in config_text.splitlines():
        if re.match(r'username\s+', line, re.IGNORECASE):
            match = re.search(r"username\s+(\S+)\s+privilege\s+(\d+)", line, re.IGNORECASE)
            if match:
                username = match.group(1)
                privilege = int(match.group(2))
                if username not in usernames:
                    usernames.add(username)
                    current_config.append(line)
        
        if any(keyword in line.lower() for keyword in ['aaa', 'tacacs', 'radius']):
            current_config.append(line)

    return {
        'usernames': sorted(list(usernames)),
        'username_count': len(usernames),
        'aaa_disabled': aaa_status,
        'compliant': not aaa_status,
        'current_config': '\n'.join(current_config)
    }

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

            # Cập nhật nội dung các ô
            current_status = []
            if results['aaa_disabled']:
                current_status.append("AAA new-model chưa được bật")
            current_status.append(f"Số lượng tài khoản local: {results['username_count']}")
            
            if results['current_config']:
                current_status.append("\nCấu hình hiện tại:")
                current_status.append(results['current_config'])

            ws.Range("F32").Value = '\n'.join(current_status)

            if results['compliant']:
                ws.Range("E32").Value = ws.Range("E4").Value
                ws.Range("G32").Value = "Không"
                ws.Range("H32").Value = ws.Range("H7").Value
            else:
                ws.Range("E32").Value = ws.Range("E5").Value
                ws.Range("G32").Value = ("Khuyến nghị:\n"
                                     "1. Bật tính năng AAA new-model\n"
                                     "2. Cấu hình xác thực tập trung qua TACACS+ hoặc RADIUS\n"
                                     "3. Giới hạn số lượng tài khoản local\n"
                                     "4. Cấu hình accounting để ghi nhận hoạt động người dùng")

            # Áp dụng font
            for cell in ["E32", "F32", "G32", "H32"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình AAA và tài khoản ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_aaa_config(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- AAA disabled: {results['aaa_disabled']}", log_file)
            log(f"- Số tài khoản: {results['username_count']}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình hiện tại:", log_file)
                for line in results['current_config'].splitlines():
                    log(f"  {line}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()