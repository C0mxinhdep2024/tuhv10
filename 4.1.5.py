import re
import logging
from pathlib import Path
from ciscoconfparse import CiscoConfParse
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

def check_routing_advertisements(config_text):
    """Kiểm tra cấu hình passive-interface cho các giao thức định tuyến động"""
    results = {
        'protocols': set(),
        'passive_default': False,
        'explicit_passive': set(),
        'no_passive': set(), 
        'has_routing': False
    }

    parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)

    # Kiểm tra các giao thức định tuyến động
    for protocol in ['router ospf', 'router rip', 'router eigrp', 'router isis']:
        protocol_configs = parse.find_objects(fr'^{protocol}')
        if protocol_configs:
            results['has_routing'] = True
            protocol_name = protocol.split()[1].upper()
            results['protocols'].add(protocol_name)
            
            for config in protocol_configs:
                # Kiểm tra passive-interface default
                if any(c.text.startswith('passive-interface default') for c in config.children):
                    results['passive_default'] = True
                    
                    # Nếu có passive default, tìm các interface được no passive
                    for child in config.children:
                        if child.text.startswith('no passive-interface'):
                            interface = child.text.split()[-1]
                            results['no_passive'].add(interface)
                else:
                    # Nếu không có passive default, tìm các interface được cấu hình passive trực tiếp
                    for child in config.children:
                        if child.text.startswith('passive-interface') and 'default' not in child.text:
                            interface = child.text.split()[-1]
                            results['explicit_passive'].add(interface)

    return results

def get_recommendations(results):
    if not results['has_routing']:
        return ""
    
    if not results['passive_default'] and not results['explicit_passive']:
        return """Khuyến nghị cấu hình passive-interface cho các giao thức định tuyến:
- Sử dụng lệnh "passive-interface default" để ngăn quảng bá trên tất cả interface.
- Sử dụng lệnh "no passive-interface" cho các interface cần quảng bá.

Ví dụ cấu hình cho OSPF:
router ospf 1
 passive-interface default
 no passive-interface GigabitEthernet0/1
"""
    return ""

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel."""
    try:
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

            if not results['has_routing']:
                sheet.Range("F25").Value = "Không phát hiện cấu hình giao thức định tuyến động"
                sheet.Range("E25").Value = sheet.Range("E6").Value
                sheet.Range("G25").Value = "Không"
                sheet.Range("H25").Value = sheet.Range("H7").Value
            elif not results['passive_default'] and not results['explicit_passive']:
                sheet.Range("F25").Value = "Thiết bị có cấu hình giao thức định tuyến nhưng chưa cấu hình passive-interface"
                sheet.Range("E25").Value = sheet.Range("E5").Value
                sheet.Range("G25").Value = get_recommendations(results)
                # Không thay đổi H25 khi chưa tuân thủ  
            else:
                status_messages = [f"Giao thức định tuyến được cấu hình: {', '.join(sorted(results['protocols']))}"]
                if results['passive_default']:
                    status_messages.append("Đã bật passive-interface default")
                    if results['no_passive']:
                        status_messages.append(f"Các interface được cấu hình no passive: {', '.join(sorted(results['no_passive']))}")
                else:
                    if results['explicit_passive']:
                        status_messages.append(f"Các interface được cấu hình passive trực tiếp: {', '.join(sorted(results['explicit_passive']))}")
                    else:
                        status_messages.append("Chưa cấu hình passive-interface")

                sheet.Range("F25").Value = "\n".join(status_messages)
                sheet.Range("E25").Value = sheet.Range("E4").Value
                sheet.Range("G25").Value = "Không"
                sheet.Range("H25").Value = sheet.Range("H7").Value

            wb.Save()
            wb.Close()
            return f"Đã cập nhật file Excel: {excel_file.name}"
        
        finally:
            excel.Quit()

    except Exception as e:
        return f"Lỗi cập nhật Excel: {str(e)}"

def main():
    """Hàm chính của script."""
    log_file = setup_logging()
    configs_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
    
    log("\n=== Bắt đầu kiểm tra cấu hình quảng bá thông tin định tuyến ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_routing_advertisements(content)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Có cấu hình giao thức định tuyến: {results['has_routing']}", log_file)
            
            if results['has_routing']:
                log(f"- Các giao thức định tuyến được cấu hình: {', '.join(sorted(results['protocols']))}", log_file)
                log(f"- Đã bật passive-interface default: {results['passive_default']}", log_file)
                log(f"- Số interface được cấu hình no passive: {len(results['no_passive'])}", log_file)
                log(f"- Số interface được cấu hình passive trực tiếp: {len(results['explicit_passive'])}", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()