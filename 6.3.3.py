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

def analyze_default_snmp_communities(config_text, default_communities):
    pattern = re.compile(r'snmp-server community (\S+)', re.MULTILINE)
    configured_communities = pattern.findall(config_text)
    
    found_defaults = set(configured_communities) & set(default_communities)

    return {
        'default_communities_found': found_defaults,
        'configured_communities': configured_communities
    }

def get_recommendations(results):
    if results['default_communities_found']:
        recommendations = [
            "Phát hiện sử dụng SNMP community mặc định:",
            *results['default_communities_found'],
            "",
            "Khuyến nghị thay đổi hoặc xóa các community mặc định.",
            "Ví dụ:",
            "! Xóa community mặc định public",
            "no snmp-server community public",
            "",
            "Các bước thực hiện:",
            "1. Xác định các community mặc định cần xóa",
            "2. Truy cập chế độ cấu hình toàn cục",
            "3. Xóa từng community mặc định bằng lệnh 'no snmp-server community <community>'",
            "4. Cấu hình community mới với tên duy nhất nếu cần",
            "5. Lưu cấu hình"
        ]
        return "\n".join(recommendations)
    return ""

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

        if results['default_communities_found']:
            sheet.Range("F47").Value = "Phát hiện sử dụng các SNMP community mặc định:\n" + "\n".join(results['default_communities_found'])
            sheet.Range("E47").Value = sheet.Range("E5").Value
            sheet.Range("G47").Value = get_recommendations(results)
        else:
            sheet.Range("F47").Value = "Không sử dụng SNMP community mặc định\nCác community đã cấu hình:\n" + "\n".join(results['configured_communities'])
            sheet.Range("E47").Value = sheet.Range("E4").Value
            sheet.Range("G47").Value = "Không"
            sheet.Range("H47").Value = sheet.Range("H7").Value

        wb.Save()
        return f"Đã cập nhật kết quả vào file: {excel_file.name}"

    finally:
        wb.Close()
        excel.Quit()

def main():
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    default_communities = ['public', 'private', 'community']
    
    log("\n=== Bắt đầu kiểm tra sử dụng SNMP community mặc định ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = analyze_default_snmp_communities(content, default_communities)
            
            log(f"- Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"  + Số community mặc định: {len(results['default_communities_found'])}", log_file)
            log(f"  + Số community đã cấu hình: {len(results['configured_communities'])}", log_file)
            
            update_result = update_excel_with_com(config_file.name, results)
            log(update_result, log_file)
            
        except Exception as e:
            log(f"Lỗi khi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()