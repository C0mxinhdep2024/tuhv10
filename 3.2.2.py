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

def check_bpduguard(config):
    """
    Kiểm tra cấu hình BPDU guard trên các access port.
    """
    results = {
        'access_ports': set(),
        'non_compliant_ports': set(),
        'bpduguard_default': False,
        'portfast_default': False
    }

    # Tìm cấu hình global
    results['bpduguard_default'] = bool(re.search(r'spanning-tree portfast bpduguard default', config))
    results['portfast_default'] = bool(re.search(r'spanning-tree portfast default', config))

    # Tìm tất cả interface blocks
    interface_blocks = re.finditer(
        r'interface\s+([^\n]+)(?:\n(?:[^\n]+))*?(?=\ninterface|\n\S|$)', 
        config,
        re.MULTILINE
    )

    for block in interface_blocks:
        interface_text = block.group(0)
        interface_name = block.group(1).strip()

        # Skip non-physical interfaces và subinterfaces
        if ('.' in interface_name or 
            any(skip in interface_name.lower() 
                for skip in ['vlan', 'port-channel', 'loopback', 'tunnel'])):
            continue

        # Kiểm tra access port
        if not re.search(r'switchport mode access|switchport access vlan', interface_text):
            continue

        results['access_ports'].add(interface_name)

        # Kiểm tra từng interface
        has_bpduguard = bool(re.search(r'spanning-tree bpduguard enable', interface_text))
        has_portfast = bool(re.search(r'spanning-tree portfast', interface_text))

        # Port được bảo vệ nếu:
        # 1. Có bpduguard trực tiếp, hoặc
        # 2. Có global bpduguard và (có portfast trực tiếp hoặc có global portfast)
        if not (has_bpduguard or 
                (results['bpduguard_default'] and 
                 (has_portfast or results['portfast_default']))):
            results['non_compliant_ports'].add(interface_name)

    return results

def get_recommendations():
    """Tạo khuyến nghị cấu hình."""
    return """Cấu hình BPDU guard trên các port access theo một trong các cách sau:

1. Cấu hình global cho tất cả portfast ports:
   spanning-tree portfast default
   spanning-tree portfast bpduguard default

2. Hoặc cấu hình trực tiếp trên từng interface:
   interface <port_name>
    spanning-tree portfast
    spanning-tree bpduguard enable"""

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel."""
    try:
        # Tìm file Excel tương ứng
        base_name = file_name.split('_')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file = next(excel_dir.glob(f"{base_name}*.xlsx"), None)
        
        if not excel_file:
            return f"Không tìm thấy file Excel cho {base_name}"

        # Khởi tạo Excel
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        
        try:
            wb = excel.Workbooks.Open(str(excel_file.absolute()))
            sheet = wb.ActiveSheet

            if not results['access_ports']:
                # Không có port access
                sheet.Range("F17").Value = "Không có port access nào trên thiết bị"
                sheet.Range("E17").Value = sheet.Range("E4").Value
                sheet.Range("G17").Value = "Không"
                sheet.Range("H17").Value = sheet.Range("H7").Value
            elif not results['non_compliant_ports']:
                # Tất cả port đã được cấu hình
                status = []
                if results['bpduguard_default']:
                    status.append("Đã bật BPDU guard mặc định")
                if results['portfast_default']:
                    status.append("Đã bật Portfast mặc định")
                status.append("Tất cả port access đã được cấu hình BPDU guard")
                
                sheet.Range("F17").Value = "\n".join(status)
                sheet.Range("E17").Value = sheet.Range("E4").Value
                sheet.Range("G17").Value = "Không"
                sheet.Range("H17").Value = sheet.Range("H7").Value
            else:
                # Có port chưa được cấu hình
                status = []
                if results['bpduguard_default']:
                    status.append("Đã bật BPDU guard mặc định")
                if results['portfast_default']:
                    status.append("Đã bật Portfast mặc định")
                status.append(f"Các port chưa được cấu hình BPDU guard: {', '.join(sorted(results['non_compliant_ports']))}")
                
                sheet.Range("F17").Value = "\n".join(status)
                sheet.Range("E17").Value = sheet.Range("E5").Value
                sheet.Range("G17").Value = get_recommendations()
                # Không thay đổi H17 khi không tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra cấu hình BPDU guard ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_bpduguard(content)
            
            # Log kết quả phân tích
            if not results['access_ports']:
                log("Không tìm thấy port access", log_file)
            else:
                if results['bpduguard_default']:
                    log("BPDU guard mặc định: Bật", log_file)
                if results['portfast_default']:
                    log("Portfast mặc định: Bật", log_file)
                    
                if results['non_compliant_ports']:
                    log("Các port chưa cấu hình BPDU guard:", log_file)
                    for port in sorted(results['non_compliant_ports']):
                        log(f"- {port}", log_file)
                else:
                    log("Tất cả port access đã được cấu hình BPDU guard", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()