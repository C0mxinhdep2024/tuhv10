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

def analyze_access_control(config_text):
    """
    Phân tích cấu hình giới hạn IP quản trị
    
    Args:
        config_text: Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích cấu hình access control
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True)
    results = {
        'compliant': True,
        'issues': [],
        'configured_acls': set(),
        'current_config': set()
    }

    try:
        # Kiểm tra access-class trên VTY lines
        vty_lines = parse.find_objects(r'^line vty')
        access_classes = set()
        
        # Tìm tất cả access-class được cấu hình
        for line in vty_lines:
            for child in line.children:
                if 'access-class' not in child.text:
                    continue
                    
                match = re.search(r'access-class (\S+) in', child.text)
                if match:
                    acl_name = match.group(1)
                    access_classes.add(acl_name)
                    results['current_config'].add(f"{line.text}\n {child.text.strip()}")

        if not access_classes:
            results['compliant'] = False
            results['issues'].append("Chưa cấu hình access-class giới hạn IP quản trị trên VTY")
        else:
            # Tìm cấu hình ACL tương ứng
            for acl_name in access_classes:
                acl_lines = parse.find_objects(
                    rf'^ip access-list.*{acl_name}|^access-list.*{acl_name}'
                )
                if acl_lines:
                    for acl_line in acl_lines:
                        results['configured_acls'].add(acl_line.text.strip())
                        if acl_line.children:
                            for child in acl_line.children:
                                results['configured_acls'].add(f" {child.text.strip()}")
                else:
                    results['compliant'] = False
                    results['issues'].append(f"Không tìm thấy cấu hình cho ACL: {acl_name}")

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
                config_text = []
                if results['current_config']:
                    config_text.append("VTY Line Configuration:")
                    config_text.extend(results['current_config'])
                if results['configured_acls']:
                    config_text.append("\nACL Configuration:")
                    config_text.extend(results['configured_acls'])
                
                ws.Range("E41").Value = ws.Range("E4").Value
                ws.Range("F41").Value = "\n".join(config_text)
                ws.Range("G41").Value = "Không"
                ws.Range("H41").Value = ws.Range("H7").Value
            else:
                ws.Range("E41").Value = ws.Range("E5").Value
                ws.Range("F41").Value = "\n".join(results['issues'])
                ws.Range("G41").Value = ("Khuyến nghị:\n"
                                     "1. Tạo ACL để giới hạn IP quản trị\n"
                                     "2. Áp dụng ACL vào các line VTY\n"
                                     "3. Chỉ cho phép các IP quản trị được phép\n\n"
                                     "Ví dụ:\n"
                                     "ip access-list standard ADMIN-ACCESS\n"
                                     " permit 192.168.1.0 0.0.0.255\n"
                                     "line vty 0 4\n"
                                     " access-class ADMIN-ACCESS in")

            # Áp dụng font
            for cell in ["E41", "F41", "G41", "H41"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình IP whitelist ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_access_control(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Compliant: {results['compliant']}", log_file)
            
            if results['current_config']:
                log("\n- Cấu hình VTY hiện tại:", log_file)
                for config in sorted(results['current_config']):
                    log(f"  {config}", log_file)
            
            if results['configured_acls']:
                log("\n- Cấu hình ACL:", log_file)
                for acl in sorted(results['configured_acls']):
                    log(f"  {acl}", log_file)
            
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