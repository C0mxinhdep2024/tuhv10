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

def analyze_config_backup(config_text):
    """
    Phân tích cấu hình backup thiết bị
    
    Args:
        config_text (str): Nội dung cấu hình thiết bị
        
    Returns:
        dict: Kết quả phân tích cấu hình backup
    """
    results = {
        'issues': [],
        'current_config': [],
        'details': {}
    }

    try:
        # Tìm cấu hình archive
        archive_match = re.search(r'(archive\n.*?(?=\n\S+|$))', config_text, re.DOTALL)
        
        if not archive_match:
            results['issues'].append("Không tìm thấy cấu hình archive")
            return results

        # Lấy khối cấu hình archive
        archive_config = archive_match.group(1)
        results['current_config'].append(archive_config)

        # Phân tích chi tiết
        # Đường dẫn lưu
        path_match = re.search(r'path\s+(\S+)', archive_config)
        results['details']['đường_dẫn_lưu'] = path_match.group(1) if path_match else 'Chưa cấu hình'

        # Kiểm tra write-memory
        write_memory = 'write-memory' in archive_config
        results['details']['tự_động_lưu'] = 'Có' if write_memory else 'Không'

        # Kiểm tra chu kỳ lưu
        time_match = re.search(r'time-period\s+(\d+)', archive_config)
        if time_match:
            time_period = int(time_match.group(1))
            results['details']['chu_kỳ_lưu'] = f"{time_period} phút"
            
            # Đánh giá chu kỳ lưu
            if time_period == 0:
                results['issues'].append("Chu kỳ lưu backup là 0 phút")
            elif time_period > 10080:  # > 7 ngày
                results['issues'].append(f"Chu kỳ lưu {time_period} phút quá dài")
        else:
            results['details']['chu_kỳ_lưu'] = 'Chưa cấu hình'
            results['issues'].append("Chưa cấu hình chu kỳ lưu backup")

    except Exception as e:
        results['issues'].append(f"Lỗi phân tích cấu hình: {str(e)}")

    return results

def get_recommendations(results):
    """
    Sinh ra các khuyến nghị dựa trên kết quả phân tích
    
    Args:
        results (dict): Kết quả phân tích cấu hình backup
    
    Returns:
        str: Chuỗi khuyến nghị
    """
    recommendations = [
        "Khuyến nghị cấu hình backup:",
        "1. Thiết lập đường dẫn lưu backup:",
        "   archive",
        "    path flash:backup/",
        "",
        "2. Bật tự động lưu cấu hình:",
        "   archive",
        "    write-memory",
        "",
        "3. Cấu hình chu kỳ lưu backup:",
        "   archive",
        "    time-period 1440  ; Lưu 1 lần/ngày",
        "",
        "Ví dụ cấu hình đầy đủ:",
        "archive",
        " path flash:backup/",
        " write-memory",
        " time-period 1440"
    ]
    
    return "\n".join(recommendations)

def update_excel_with_com(file_name, results):
    """Cập nhật kết quả vào file Excel sử dụng COM interface"""
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
            ws = wb.ActiveSheet

            # Chuẩn bị thông tin chi tiết
            details = [
                f"Đường dẫn backup: {results['details'].get('đường_dẫn_lưu', 'Chưa cấu hình')}",
                f"Tự động lưu cấu hình: {results['details'].get('tự_động_lưu', 'Không')}",
                f"Chu kỳ backup: {results['details'].get('chu_kỳ_lưu', 'Chưa cấu hình')}"
            ]

            if not results['issues']:
                # Trường hợp tuân thủ
                ws.Range("E31").Value = ws.Range("E4").Value
                ws.Range("F31").Value = "\n".join(details + results['current_config'])
                ws.Range("G31").Value = "Không"
                ws.Range("H31").Value = ws.Range("H7").Value
            else:
                # Trường hợp không tuân thủ
                ws.Range("E31").Value = ws.Range("E5").Value
                ws.Range("F31").Value = "\n".join(details + results['current_config'] + ["\nCác vấn đề:"] + results['issues'])
                ws.Range("G31").Value = get_recommendations(results)

            # Áp dụng font
            for cell in ["E31", "F31", "G31", "H31"]:
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
    
    log("\n=== Bắt đầu kiểm tra cấu hình backup ===", log_file)
    
    for config_file in configs_dir.glob("*.[lt][xo][tg]"):
        try:
            log(f"\nĐang xử lý: {config_file.name}", log_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = f.read()
            
            results = analyze_config_backup(config)
            
            # Log kết quả phân tích
            log(f"\nKết quả phân tích cho {config_file.name}:", log_file)
            
            if results['details']:
                log("Chi tiết cấu hình:", log_file)
                for key, value in results['details'].items():
                    log(f"- {key}: {value}", log_file)
            
            if results['issues']:
                log("\nCác vấn đề phát hiện:", log_file)
                for issue in results['issues']:
                    log(f"- {issue}", log_file)
            
            # Cập nhật Excel - truyền config_file.name thay vì config_file
            result = update_excel_with_com(config_file.name, results)
            log(result, log_file)
            
        except Exception as e:
            log(f"Lỗi xử lý file {config_file.name}: {str(e)}", log_file)

if __name__ == "__main__":
    main()