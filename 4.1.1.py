import re
from pathlib import Path
import win32com.client
import os

# --- Cấu hình logging đơn giản ---
def setup_logging():
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    """Ghi log ra file và console."""
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def check_gateway_redundancy(config):
    """
    Kiểm tra cấu hình xác thực cho các giao thức dự phòng gateway (HSRP, VRRP)
    """
    results = {
        'protocols': {
            'hsrp': {'used': False, 'auth': False},
            'vrrp': {'used': False, 'auth': False}
        },
        'evidence': [],
        'compliant': False
    }

    # Kiểm tra HSRP
    hsrp_configs = re.finditer(r'interface\s+([^\n]+)(?:\n[^\n]+)*?(?:\s+standby\s+\d+[^\n]+\n)+', config, re.M)
    for match in hsrp_configs:
        results['protocols']['hsrp']['used'] = True
        interface_config = match.group(0)
        
        if re.search(r'standby\s+\d+\s+authentication', interface_config):
            results['protocols']['hsrp']['auth'] = True
            results['evidence'].append(interface_config.strip())

    # Kiểm tra VRRP
    vrrp_configs = re.finditer(r'interface\s+([^\n]+)(?:\n[^\n]+)*?(?:\s+vrrp\s+\d+[^\n]+\n)+', config, re.M)
    for match in vrrp_configs:
        results['protocols']['vrrp']['used'] = True
        interface_config = match.group(0)
        
        if re.search(r'vrrp\s+\d+\s+authentication', interface_config):
            results['protocols']['vrrp']['auth'] = True
            results['evidence'].append(interface_config.strip())

    # Xác định trạng thái tuân thủ
    protocols_used = [p for p, v in results['protocols'].items() if v['used']]
    if not protocols_used:
        results['compliant'] = None  # Không áp dụng
    else:
        results['compliant'] = all(v['auth'] for p, v in results['protocols'].items() if v['used'])

    return results

def get_recommendations():
    """Tạo khuyến nghị cấu hình."""
    return """Cấu hình xác thực cho các giao thức dự phòng gateway:

1. HSRP Authentication:
   interface <interface_name>
    standby <group> authentication md5 key-string <key>

2. VRRP Authentication:
   interface <interface_name>
    vrrp <group> authentication text <key>"""

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel sử dụng COM."""
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

            protocols_used = [p for p, v in results['protocols'].items() if v['used']]
            
            if not protocols_used:
                # Không áp dụng - không có giao thức dự phòng
                sheet.Range("F21").Value = "Không có cấu hình giao thức dự phòng gateway"
                sheet.Range("E21").Value = sheet.Range("E6").Value
                sheet.Range("G21").Value = "Không"
                sheet.Range("H21").Value = sheet.Range("H7").Value
            elif results['compliant']:
                # Tuân thủ - có xác thực
                status = []
                for protocol, info in results['protocols'].items():
                    if info['used']:
                        status.append(f"{protocol.upper()} đã được cấu hình với xác thực")
                sheet.Range("F21").Value = "\n".join(status)
                sheet.Range("E21").Value = sheet.Range("E4").Value
                sheet.Range("G21").Value = "Không"
                sheet.Range("H21").Value = sheet.Range("H7").Value
            else:
                # Không tuân thủ - thiếu xác thực
                status = []
                for protocol, info in results['protocols'].items():
                    if info['used'] and not info['auth']:
                        status.append(f"{protocol.upper()} được cấu hình nhưng chưa có xác thực")
                sheet.Range("F21").Value = "\n".join(status)
                sheet.Range("E21").Value = sheet.Range("E5").Value
                sheet.Range("G21").Value = get_recommendations()
                # Không thay đổi H21 khi không tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra xác thực giao thức dự phòng gateway ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_gateway_redundancy(content)
            
            # Log kết quả phân tích
            protocols_used = [p for p, v in results['protocols'].items() if v['used']]
            if not protocols_used:
                log("Không có cấu hình giao thức dự phòng gateway", log_file)
            else:
                for protocol, info in results['protocols'].items():
                    if info['used']:
                        status = "có" if info['auth'] else "không có"
                        log(f"{protocol.upper()}: {status} xác thực", log_file)
                        
                if results['evidence']:
                    log("\nCấu hình hiện tại:", log_file)
                    for evidence in results['evidence']:
                        log(evidence, log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()