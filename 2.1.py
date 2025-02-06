import re
from pathlib import Path
import win32com.client
import os

# --- Cấu hình logging ---
current_module_name = Path(__file__).stem
result_log_name = f"Result_{current_module_name.replace('.', ',')}.txt"
RESULT_LOG_FILE = Path(result_log_name)

if RESULT_LOG_FILE.exists():
    RESULT_LOG_FILE.unlink()

_original_print = print
def print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    message = sep.join(map(str, args)) + end
    _original_print(*args, **kwargs)
    with RESULT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(message)

def check_port_status(show_output):
    """
    Phân tích output của lệnh 'show ip interface brief' để kiểm tra trạng thái cổng.
    
    Args:
        show_output (str): Nội dung output của lệnh show ip interface brief
        
    Returns:
        dict: Dictionary chứa danh sách cổng không sử dụng và đề xuất
    """
    try:
        results = {
            'unused_ports': [],
            'recommendations': []
        }

        # Bỏ qua dòng header và xử lý từng interface
        lines = [line.strip() for line in show_output.split('\n') if line.strip() and not line.startswith('Interface')]
        
        for line in lines:
            parts = line.split()
            if len(parts) >= 6:  # Đảm bảo đủ các trường cần thiết
                interface = parts[0]
                ip = parts[1]
                status = parts[4]
                protocol = parts[5]
                
                # Loại bỏ các subinterface (interface có chứa dấu chấm)
                if '.' in interface:
                    continue
                
                # Kiểm tra các cổng physical interface chưa được shutdown
                if (ip == 'unassigned' and 
                    status != 'administratively' and 
                    protocol == 'down' and
                    any(interface.startswith(prefix) for prefix in ['Gi', 'Te', 'Fa', 'Eth'])):
                    results['unused_ports'].append(f"{interface} {status}")
        
        if results['unused_ports']:
            results['recommendations'].append("Shutdown các cổng vật lý chưa tắt")
        
        return results

    except Exception as e:
        print(f"[LỖI] Phân tích trạng thái cổng thất bại: {str(e)}")
        return None

def update_excel_with_com(file_name, results):
    """
    Cập nhật kết quả vào file Excel sử dụng Win32COM.
    
    Args:
        file_name (str): Tên file log đang xử lý
        results (dict): Kết quả phân tích trạng thái cổng
    """
    try:
        # Xử lý tên file để tìm file Excel tương ứng
        base_name = file_name.split('_')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file_path = next(excel_dir.glob(f"{base_name}*.xlsx"), None)
        
        if not excel_file_path:
            print(f"[CẢNH BÁO] File Excel cho {base_name} không tồn tại.")
            return

        # Chuyển đổi sang đường dẫn tuyệt đối cho Win32COM
        abs_path = os.path.abspath(excel_file_path)

        # Khởi tạo Excel application
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False  # Chạy ẩn Excel để tránh giao diện nháy
        
        try:
            # Mở workbook và lấy sheet active
            wb = excel.Workbooks.Open(abs_path)
            sheet = wb.ActiveSheet

            # Cập nhật các ô trong Excel
            if results and results['unused_ports']:
                # Không tuân thủ - có cổng cần shutdown
                sheet.Range("F13").Value = f"Các cổng vật lý chưa được tắt:\n" + '\n'.join(results['unused_ports'])
                sheet.Range("G13").Value = f"Đề xuất: {results['recommendations'][0]}"
                sheet.Range("E13").Value = sheet.Range("E5").Value  # Không tuân thủ
            else:
                # Tuân thủ - các cổng đã shutdown
                sheet.Range("F13").Value = "Các cổng vật lý không sử dụng đều được shutdown"
                sheet.Range("G13").Value = "Không"
                sheet.Range("E13").Value = sheet.Range("E4").Value  # Tuân thủ
                sheet.Range("H13").Value = sheet.Range("H7").Value

            # Lưu và đóng file
            wb.Save()
            wb.Close()
            print(f"[THÔNG BÁO] Đã cập nhật file Excel: {excel_file_path.name}")

        finally:
            # Đảm bảo luôn đóng Excel để tránh treo process
            excel.Quit()

    except Exception as e:
        print(f"[LỖI] Cập nhật Excel thất bại: {str(e)}")

def main():
    """
    Hàm chính điều phối quá trình kiểm tra cổng và cập nhật Excel.
    """
    try:
        # Thiết lập đường dẫn
        log_folder_path = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
        
        print("\n=== Bắt đầu kiểm tra trạng thái cổng ===")
        
        # Xử lý từng file log
        for log_file in log_folder_path.glob("*.[lt][xo][tg]"):
            try:
                print(f"\n--- Đang xử lý file: {log_file.name} ---")
                
                # Đọc và phân tích nội dung file
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Kiểm tra trạng thái cổng
                results = check_port_status(content)
                
                if results:
                    print("Kết quả phân tích:")
                    if results['unused_ports']:
                        print("Các cổng không sử dụng và chưa shutdown:")
                        for port in results['unused_ports']:
                            print(f"- {port}")
                        print(f"Đề xuất: {results['recommendations'][0]}")
                    else:
                        print("Tất cả các cổng không sử dụng đều đã được shutdown")
                    
                    # Cập nhật Excel sử dụng COM
                    update_excel_with_com(log_file.name, results)
                else:
                    print(f"[CẢNH BÁO] Không tìm thấy thông tin trong file {log_file.name}")
                    
            except Exception as e:
                print(f"[LỖI] Xử lý file {log_file.name} thất bại: {str(e)}")
                continue
                
    except Exception as e:
        print(f"[LỖI] Lỗi chung trong quá trình xử lý: {str(e)}")

if __name__ == '__main__':
    main()