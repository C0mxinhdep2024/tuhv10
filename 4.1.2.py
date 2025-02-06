import re
from pathlib import Path
import win32com.client
import os

def setup_logging():
    log_file = Path(f"Result_{Path(__file__).stem.replace('.', ',')}.txt")
    if log_file.exists():
        log_file.unlink()
    return log_file

def log(message, log_file):
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")

def check_igp_authentication(config):
    """Kiểm tra xác thực cho các giao thức IGP (RIP, OSPF, ISIS)."""
    results = {
        'protocols': {
            'rip': {'configured': False, 'auth': False, 'evidence': []},
            'ospf': {'configured': False, 'auth': False, 'evidence': []},
            'isis': {'configured': False, 'auth': False, 'evidence': []}
        },
        'compliant': False
    }

    # Kiểm tra RIP
    rip_config = re.finditer(r'router rip\s*(?:\n[^\n]+)*?(?=\nrouter|\n\S|$)', config, re.M)
    for match in rip_config:
        config_text = match.group(0)
        results['protocols']['rip']['configured'] = True
        if re.search(r'key chain|message-digest', config_text):
            results['protocols']['rip']['auth'] = True
            results['protocols']['rip']['evidence'].append(config_text.strip())

    # Kiểm tra OSPF
    ospf_configs = re.finditer(r'router ospf\s*(?:\n[^\n]+)*?(?=\nrouter|\n\S|$)', config, re.M)
    for match in ospf_configs:
        config_text = match.group(0)
        results['protocols']['ospf']['configured'] = True
        if re.search(r'area .* authentication|ip ospf authentication', config_text):
            results['protocols']['ospf']['auth'] = True
            results['protocols']['ospf']['evidence'].append(config_text.strip())

    # Kiểm tra ISIS
    isis_configs = re.finditer(r'router isis\s*(?:\n[^\n]+)*?(?=\nrouter|\n\S|$)', config, re.M)
    for match in isis_configs:
        config_text = match.group(0)
        results['protocols']['isis']['configured'] = True
        if re.search(r'authentication mode|authentication key-chain', config_text):
            results['protocols']['isis']['auth'] = True
            results['protocols']['isis']['evidence'].append(config_text.strip())

    # Xác định trạng thái tuân thủ
    protocols_used = [p for p, v in results['protocols'].items() if v['configured']]
    if not protocols_used:
        results['compliant'] = None  # Không áp dụng
    else:
        results['compliant'] = all(v['auth'] for p, v in results['protocols'].items() if v['configured'])

    return results

def get_recommendations():
    """Tạo khuyến nghị cấu hình."""
    return """Cấu hình xác thực cho các giao thức định tuyến:

1. RIP Authentication:
   key chain <name>
    key 1
     key-string <key>
   interface <name>
    ip rip authentication key-chain <name>
    ip rip authentication mode md5

2. OSPF Authentication:
   router ospf <process-id>
    area <area-id> authentication message-digest
   interface <name>
    ip ospf message-digest-key 1 md5 <key>
    ip ospf authentication message-digest

3. IS-IS Authentication:
   key chain <name>
    key 1
     key-string <key>
   router isis
    authentication mode md5 level-1-2
    authentication key-chain <name> level-1-2"""

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

            protocols_used = [p for p, v in results['protocols'].items() if v['configured']]
            
            if not protocols_used:
                # Không áp dụng - không có giao thức IGP
                sheet.Range("F22").Value = "Không có cấu hình giao thức IGP"
                sheet.Range("E22").Value = sheet.Range("E6").Value
                sheet.Range("G22").Value = "Không"
                sheet.Range("H22").Value = sheet.Range("H7").Value
            elif results['compliant']:
                # Tuân thủ - có xác thực
                status = []
                for protocol, info in results['protocols'].items():
                    if info['configured']:
                        status.append(f"{protocol.upper()} đã được cấu hình với xác thực:")
                        status.extend(info['evidence'])
                sheet.Range("F22").Value = "\n".join(status)
                sheet.Range("E22").Value = sheet.Range("E4").Value
                sheet.Range("G22").Value = "Không"
                sheet.Range("H22").Value = sheet.Range("H7").Value
            else:
                # Không tuân thủ - thiếu xác thực
                status = []
                for protocol, info in results['protocols'].items():
                    if info['configured'] and not info['auth']:
                        status.append(f"{protocol.upper()} được cấu hình nhưng chưa có xác thực")
                sheet.Range("F22").Value = "\n".join(status)
                sheet.Range("E22").Value = sheet.Range("E5").Value
                sheet.Range("G22").Value = get_recommendations()
                # Không thay đổi H22 khi không tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra xác thực giao thức IGP ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_igp_authentication(content)
            
            # Log kết quả phân tích
            protocols_used = [p for p, v in results['protocols'].items() if v['configured']]
            if not protocols_used:
                log("Không có cấu hình giao thức IGP", log_file)
            else:
                for protocol, info in results['protocols'].items():
                    if info['configured']:
                        status = "có" if info['auth'] else "không có"
                        log(f"{protocol.upper()}: {status} xác thực", log_file)
                        if info['evidence']:
                            log("\nCấu hình hiện tại:", log_file)
                            for evidence in info['evidence']:
                                log(evidence, log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()