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

def analyze_ntp_config(config_text):
    """
    Phân tích cấu hình NTP server
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích cấu hình NTP
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': True,
        'issues': [],
        'ntp_servers': set(),
        'current_config': []
    }

    try:
        # Tìm tất cả cấu hình NTP server
        ntp_configs = parse.find_objects(r'^ntp server')
        
        if not ntp_configs:
            results['compliant'] = False
            results['issues'].append("Chưa cấu hình NTP server")
        else:
            for config in ntp_configs:
                server = config.text.replace('ntp server ', '').strip()
                results['ntp_servers'].add(server)
                results['current_config'].append(config.text)
                
            # Kiểm tra các thông số cấu hình NTP khác
            other_ntp_configs = parse.find_objects(r'^ntp')
            for config in other_ntp_configs:
                if not config.text.startswith('ntp server'):
                    results['current_config'].append(config.text)

            results['current_config'].sort()

    except Exception as e:
        results['issues'].append(f"Lỗi khi phân tích cấu hình: {str(e)}")
        results['compliant'] = False

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
                config_text = [f"Đã cấu hình các NTP server:"]
                if results['ntp_servers']:
                    servers_str = ", ".join(sorted(results['ntp_servers']))
                    config_text.append(f"- Servers: {servers_str}")
                
                if results['current_config']:
                    config_text.append("\nCấu hình chi tiết:")
                    config_text.extend(results['current_config'])
                
                ws.Range("E43").Value = ws.Range("E4").Value
                ws.Range("F43").Value = "\n".join(config_text)
                ws.Range("G43").Value = "Không"
                ws.Range("H43").Value = ws.Range("H7").Value
            else:
                ws.Range("E43").Value = ws.Range("E5").Value
                ws.Range("F43").Value = "\n".join(results['issues'])
                ws.Range("G43").Value = ("Khuyến nghị:\n"
                                     "1. Cấu hình ít nhất một NTP server\n"
                                     "2. Sử dụng nhiều server để dự phòng\n"
                                     "3. Ưu tiên sử dụng NTP server nội bộ\n\n"
                                     "Ví dụ:\n"
                                     "ntp server 192.168.1.1\n"
                                     "ntp server 192.168.1.2")

            # Áp dụng font
            for cell in ["E43", "F43", "G43", "H43"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình NTP ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_ntp_config(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            
            if results['ntp_servers']:
                log("\n- NTP servers đã cấu hình:", log_file)
                for server in sorted(results['ntp_servers']):
                    log(f"  - {server}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình chi tiết:", log_file)
                for config in results['current_config']:
                    log(f"  {config}", log_file)
            
            if results['issues']:
                log("\n- Các vấn đề phát hiện:", log_file)
                for issue in results['issues']:
                    log(f"  - {issue}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()