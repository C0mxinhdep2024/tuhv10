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

def analyze_snmp_v3_config(config_text):
    snmp_v3_pattern = re.compile(r'snmp-server group.*v3', re.MULTILINE)
    return {
        'snmp_v3_configured': bool(snmp_v3_pattern.search(config_text)),
        'snmp_v3_config': snmp_v3_pattern.findall(config_text)
    }

def get_recommendations(results):
    if not results['snmp_v3_configured']:
        return "Cấu hình SNMPv3 để tăng cường bảo mật"
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

        if results['snmp_v3_configured']:
            sheet.Range("F45").Value = "Đã cấu hình SNMPv3:\n" + "\n".join(results['snmp_v3_config'])
            sheet.Range("E45").Value = sheet.Range("E4").Value
            sheet.Range("G45").Value = "Không"
            sheet.Range("H45").Value = sheet.Range("H7").Value  
        else:
            sheet.Range("F45").Value = "Chưa cấu hình SNMPv3"
            sheet.Range("E45").Value = sheet.Range("E5").Value
            sheet.Range("G45").Value = get_recommendations(results)

        wb.Save()
        return f"Đã cập nhật kết quả vào file: {excel_file.name}"

    finally:
        wb.Close()
        excel.Quit()

def main():
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra cấu hình SNMP Version ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = analyze_snmp_v3_config(content)
            
            log(f"- Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"  + Cấu hình SNMPv3: {'Có' if results['snmp_v3_configured'] else 'Không'}", log_file)
            
            update_result = update_excel_with_com(config_file.name, results)
            log(update_result, log_file)
            
        except Exception as e:
            log(f"Lỗi khi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()