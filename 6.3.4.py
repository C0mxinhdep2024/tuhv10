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

def analyze_snmp_access_control(config_text):
    acl_pattern = re.compile(r'snmp-server community\s+\S+\s+(?:view\s+\S+\s+)?(?:RO|RW)\s+(\S+)', re.MULTILINE)
    host_pattern = re.compile(r'snmp-server host\s+(\S+)', re.MULTILINE)

    acls = acl_pattern.findall(config_text)
    hosts = host_pattern.findall(config_text)

    return {
        'access_control_configured': bool(acls or hosts),
        'acls': acls,
        'hosts': hosts
    }

def get_recommendations():
    return """Khuyến nghị cấu hình giới hạn truy cập SNMP:
1. Sử dụng ACL để chỉ cho phép các host tin cậy truy cập SNMP:
   snmp-server community <community> RO <acl>

2. Chỉ định các host cụ thể được phép truy cập SNMP:
   snmp-server host <ip_address> version <version> <community>

Ví dụ:
! Cấu hình ACL cho phép subnet 10.10.10.0/24 truy cập qua SNMP  
access-list 10 permit 10.10.10.0 0.0.0.255
snmp-server community mgmt_comm RO 10

! Cho phép host 10.10.10.100 truy cập SNMP
snmp-server host 10.10.10.100 version 2c mgmt_comm
"""

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

        if results['access_control_configured']:
            sheet.Range("F48").Value = "Đã cấu hình giới hạn truy cập SNMP:\n\nACLs:\n" + "\n".join(results['acls']) + "\n\nHosts:\n" + "\n".join(results['hosts'])
            sheet.Range("E48").Value = sheet.Range("E4").Value
            sheet.Range("G48").Value = "Không"
            sheet.Range("H48").Value = sheet.Range("H7").Value
        else:
            sheet.Range("F48").Value = "Chưa cấu hình giới hạn truy cập SNMP"
            sheet.Range("E48").Value = sheet.Range("E5").Value
            sheet.Range("G48").Value = get_recommendations()

        wb.Save()
        return f"Đã cập nhật kết quả vào file: {excel_file.name}"

    finally:
        wb.Close()  
        excel.Quit()

def main():
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra cấu hình giới hạn truy cập SNMP ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = analyze_snmp_access_control(content)
            
            log(f"- Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"  + Có cấu hình giới hạn truy cập SNMP: {results['access_control_configured']}", log_file)
            
            update_result = update_excel_with_com(config_file.name, results)
            log(update_result, log_file)
            
        except Exception as e:
            log(f"Lỗi khi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()