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

def analyze_snmp_community_permissions(config_text):
    ro_pattern = re.compile(r'snmp-server community\s+\S+\s+RO', re.MULTILINE | re.IGNORECASE)
    rw_pattern = re.compile(r'snmp-server community\s+\S+\s+RW', re.MULTILINE | re.IGNORECASE)

    ro_communities = ro_pattern.findall(config_text)
    rw_communities = rw_pattern.findall(config_text)

    return {
        'ro_communities': ro_communities,
        'rw_communities': rw_communities
    }

def get_recommendations(results):
    if results['rw_communities']:
        recommendations = [
            "Thay đổi quyền các community sau sang read-only:",
            *results['rw_communities'],
            "",
            "Ví dụ cấu hình:",
            "! Thay đổi community readwritecom sang read-only",
            "snmp-server community readwritecom RO",
            "",
            "Các bước thực hiện:",
            "1. Xác định các community cần thay đổi (có quyền RW)",  
            "2. Sao lưu cấu hình hiện tại",
            "3. Truy cập chế độ cấu hình toàn cục (configure terminal)",
            "4. Xóa cấu hình community cũ (no snmp-server community <community>)",
            "5. Thêm lại community với quyền read-only (snmp-server community <community> RO)",
            "6. Lưu cấu hình (write memory)"
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

        if not results['rw_communities']:
            sheet.Range("F46").Value = "Tất cả community đã được cấu hình read-only:\n" + "\n".join(results['ro_communities'])
            sheet.Range("E46").Value = sheet.Range("E4").Value
            sheet.Range("G46").Value = "Không"
            sheet.Range("H46").Value = sheet.Range("H7").Value
        else:
            sheet.Range("F46").Value = "Phát hiện các community có quyền read-write:\n" + "\n".join(results['rw_communities'])
            sheet.Range("E46").Value = sheet.Range("E5").Value
            sheet.Range("G46").Value = get_recommendations(results)

        wb.Save()
        return f"Đã cập nhật kết quả vào file: {excel_file.name}"

    finally:
        wb.Close()
        excel.Quit()

def main():
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra quyền của SNMP community ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = analyze_snmp_community_permissions(content)
            
            log(f"- Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"  + Số community read-only: {len(results['ro_communities'])}", log_file)
            log(f"  + Số community read-write: {len(results['rw_communities'])}", log_file)
            
            update_result = update_excel_with_com(config_file.name, results)
            log(update_result, log_file)
            
        except Exception as e:
            log(f"Lỗi khi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()