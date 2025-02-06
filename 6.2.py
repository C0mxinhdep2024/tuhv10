import re
import logging
from pathlib import Path
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

def analyze_log_config(config_text):
    buffered_logging_pattern = re.compile(r'^logging buffered', re.MULTILINE)
    host_logging_pattern = re.compile(r'^logging host', re.MULTILINE) 
    
    buffered_logging = buffered_logging_pattern.findall(config_text)
    logging_hosts = host_logging_pattern.findall(config_text)

    return {
        'buffered_logging_configured': bool(buffered_logging),
        'logging_hosts_configured': bool(logging_hosts),
        'number_of_logging_hosts': len(logging_hosts),
        'buffered_logging_config': buffered_logging[0] if buffered_logging else None
    }

def get_recommendations(results):
    recommendations = []
    
    if not results['logging_hosts_configured']:
        recommendations.append(
            "Cấu hình gửi log về logging server để lưu trữ tập trung\n"
            "Ví dụ:\n"
            "logging host 10.10.10.100\n"
            "logging host 10.10.10.101 transport tcp port 514"
        )
        
    if not results['buffered_logging_configured']:  
        recommendations.append(
            "Cấu hình logging buffered để lưu đệm log cục bộ trên thiết bị\n"
            "Ví dụ:\n"
            "logging buffered 16384 informational"
        )
    
    if recommendations:
        recommendations.insert(0, "Các bước thực hiện:")
        recommendations.append(
            "1. Truy cập chế độ cấu hình toàn cục\n"
            "2. Thực hiện cấu hình như ví dụ\n"  
            "3. Lưu cấu hình"
        )

    return "\n".join(recommendations)

def update_excel_with_com(file_name, results):
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
        
        if results['logging_hosts_configured'] and results['buffered_logging_configured']:
            # Đã cấu hình đầy đủ
            sheet.Range("F44").Value = (
                "Đã cấu hình gửi log về server:\n"
                f"- Số logging host: {results['number_of_logging_hosts']}\n\n"
                f"Đã cấu hình logging buffered:\n{results['buffered_logging_config']}"  
            )
            sheet.Range("E44").Value = sheet.Range("E4").Value  
            sheet.Range("G44").Value = "Không"
            
            # Chỉ cập nhật H44 khi tuân thủ
            sheet.Range("H44").Value = sheet.Range("H7").Value  
            
        else:
            issues = []
            if not results['logging_hosts_configured']:
                issues.append("Chưa cấu hình gửi log về logging server")
            if not results['buffered_logging_configured']:
                issues.append("Chưa cấu hình logging buffered")
                
            sheet.Range("F44").Value = "\n".join(issues)
            sheet.Range("E44").Value = sheet.Range("E5").Value
            sheet.Range("G44").Value = get_recommendations(results)
            
            # Không thay đổi H44 khi chưa tuân thủ
        
        wb.Save() 
        return f"Đã cập nhật kết quả vào file: {excel_file.name}"
    
    finally:
        wb.Close()
        excel.Quit()

def main():
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra cấu hình Logging ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"): 
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = analyze_log_config(content)
            
            log(f"- Kết quả phân tích cho {config_file.name}:", log_file)  
            log(f"  + Cấu hình logging server: {results['logging_hosts_configured']}", log_file)
            log(f"  + Số lượng logging host: {results['number_of_logging_hosts']}", log_file)
            log(f"  + Cấu hình logging buffered: {results['buffered_logging_configured']}", log_file)
            
            update_result = update_excel_with_com(config_file.name, results)
            log(update_result, log_file)
            
        except Exception as e:
            log(f"Lỗi khi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()