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

def check_bgp_authentication(config_text: str):
    """
    Kiểm tra xác thực cho BGP
    Args:
        config_text: Nội dung cấu hình thiết bị
    Returns:
        Kết quả kiểm tra BGP
    """
    parse = CiscoConfParse(config_text.splitlines(), factory=True, ignore_blank_lines=True)
    
    bgp_pattern = re.compile(r'^router bgp')
    neighbor_pattern = re.compile(r'^neighbor (\S+)')
    password_pattern = re.compile(r'password')
    keychain_pattern = re.compile(r'key-chain')

    results = {
        "configured": False,
        "auth_configured": False,
        "neighbors": []
    }

    # Kiểm tra BGP configuration
    bgp_cmds = parse.find_objects(bgp_pattern)
    if bgp_cmds:
        results["configured"] = True
        
        # Kiểm tra từng neighbor
        for cmd in bgp_cmds:
            neighbors = [c for c in cmd.children if neighbor_pattern.search(c.text)]
            for neighbor in neighbors:
                address_match = neighbor_pattern.search(neighbor.text)
                if address_match:
                    address = address_match.group(1)
                    
                    has_password = any(password_pattern.search(child.text) for child in neighbor.children)
                    has_keychain = any(keychain_pattern.search(child.text) for child in neighbor.children)
                    
                    results["neighbors"].append({
                        "address": address,
                        "has_auth": has_password or has_keychain,
                        "auth_type": "password" if has_password else ("keychain" if has_keychain else None)
                    })
        
        # Kiểm tra nếu tất cả peers đều có xác thực
        if results["neighbors"] and all(n["has_auth"] for n in results["neighbors"]):
            results["auth_configured"] = True

    return results

def get_recommendations(results):
    if not results["configured"]:
        return """Khuyến nghị cấu hình xác thực cho các BGP peer:
- Sử dụng password hoặc key chain để xác thực.
- Cấu hình xác thực trên mỗi neighbor.

Ví dụ cấu hình với password:
neighbor <peer-ip> password <password>

Ví dụ cấu hình với key chain:
key chain <key-chain-name>
 key 1
  key-string <key-string>
!
router bgp <as-number>
 neighbor <peer-ip> key-chain <key-chain-name>
"""
    if not results["auth_configured"]:
        return """Một số BGP peer chưa cấu hình xác thực, cần bổ sung để đảm bảo an toàn:
- Xác định các neighbor chưa có xác thực.
- Cấu hình xác thực cho từng neighbor bằng password hoặc key chain.

Ví dụ cấu hình với password:
neighbor <peer-ip> password <password>

Ví dụ cấu hình với key chain:  
key chain <key-chain-name>
 key 1
  key-string <key-string> 
!
router bgp <as-number>
 neighbor <peer-ip> key-chain <key-chain-name>
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

            if not results["configured"]:
                # Không có cấu hình BGP
                sheet.Range("F23").Value = "Thiết bị không có cấu hình BGP"
                sheet.Range("E23").Value = sheet.Range("E6").Value
                sheet.Range("G23").Value = "Không"
                sheet.Range("H23").Value = sheet.Range("H7").Value
            elif results["auth_configured"]:
                # Đã cấu hình xác thực đầy đủ
                status_messages = ["Hiện trạng: Đã cấu hình xác thực cho tất cả BGP peer"]
                for neighbor in results["neighbors"]:
                    status_messages.append(
                        f"- Neighbor {neighbor['address']} - Xác thực: {neighbor['auth_type']}")
                sheet.Range("F23").Value = "\n".join(status_messages)
                sheet.Range("E23").Value = sheet.Range("E4").Value
                sheet.Range("G23").Value = "Không"
                sheet.Range("H23").Value = sheet.Range("H7").Value
            else:
                # Có BGP nhưng chưa cấu hình xác thực đầy đủ
                status_messages = ["Hiện trạng: Một số BGP peer chưa cấu hình xác thực"]
                for neighbor in results["neighbors"]:
                    if not neighbor["has_auth"]:
                        status_messages.append(
                            f"- Neighbor {neighbor['address']} chưa có cấu hình xác thực")
                sheet.Range("F23").Value = "\n".join(status_messages)
                sheet.Range("E23").Value = sheet.Range("E5").Value
                sheet.Range("G23").Value = get_recommendations(results)
                # Không thay đổi H23 khi chưa tuân thủ

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
    
    log("\n=== Bắt đầu kiểm tra xác thực BGP ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            results = check_bgp_authentication(content)
            
            # Log kết quả phân tích
            log(f"Kết quả phân tích cho {config_file.name}:", log_file)
            log(f"- Có cấu hình BGP: {results['configured']}", log_file)
            log(f"- Đã xác thực cho tất cả peer: {results['auth_configured']}", log_file)
            log(f"\nThông tin chi tiết:", log_file)
            for neighbor in results["neighbors"]:
                log(f"- Neighbor {neighbor['address']} - Xác thực: {neighbor['has_auth']} ({neighbor['auth_type']})", log_file)
            
            # Cập nhật Excel
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
                
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()