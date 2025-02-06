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

def analyze_insecure_protocols(config_text):
    """
    Kiểm tra và xác định các giao thức quản trị không an toàn
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích giao thức không an toàn
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': True,
        'issues': [],
        'current_config': [],
        'recommendations': []
    }

    try:
        # Kiểm tra telnet trên các line VTY
        vty_lines = parse.find_objects(r'^line vty')
        for line in vty_lines:
            transport_inputs = [child.text for child in line.children if 'transport input' in child.text]
            for transport in transport_inputs:
                if 'telnet' in transport.lower():
                    results['compliant'] = False
                    results['issues'].append(
                        f"Telnet được bật trên {line.text}: {transport.strip()}")
                    results['recommendations'].append(
                        f"Cấu hình 'transport input ssh' cho {line.text}")
                results['current_config'].append(f"{line.text}")
                results['current_config'].append(f"  {transport.strip()}")

        # Kiểm tra HTTP server
        http_configs = parse.find_objects(r'^ip http server')
        if http_configs:
            results['compliant'] = False
            results['issues'].append("HTTP server đang được bật")
            results['recommendations'].append("Sử dụng lệnh 'no ip http server' để tắt HTTP")
            for config in http_configs:
                results['current_config'].append(config.text)

        if not results['issues']:
            results['current_config'].append("Đã tắt các giao thức không an toàn")

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
                ws.Range("E39").Value = ws.Range("E4").Value
                ws.Range("F39").Value = "\n".join(results['current_config'])
                ws.Range("G39").Value = "Không"
                ws.Range("H39").Value = ws.Range("H7").Value
            else:
                ws.Range("E39").Value = ws.Range("E5").Value
                ws.Range("F39").Value = "\n".join(results['issues'])
                if results['recommendations']:
                    ws.Range("G39").Value = "\n".join(results['recommendations'])

            # Áp dụng font
            for cell in ["E39", "F39", "G39", "H39"]:
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
    
    log("\n=== Bắt đầu kiểm tra giao thức quản trị không an toàn ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_insecure_protocols(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình hiện tại:", log_file)
                for config in results['current_config']:
                    log(f"  {config}", log_file)
            
            if results['issues']:
                log("\n- Các vấn đề phát hiện:", log_file)
                for issue in results['issues']:
                    log(f"  - {issue}", log_file)
            
            if results['recommendations']:
                log("\n- Khuyến nghị:", log_file)
                for rec in results['recommendations']:
                    log(f"  - {rec}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()