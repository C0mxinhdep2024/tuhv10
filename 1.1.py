import re
from pathlib import Path
import win32com.client
import os

# --- Phần mới: Ghi đè hàm print để ghi log vào file tổng hợp ---
# Lấy tên module hiện tại và chuyển đổi dấu chấm thành dấu phẩy
current_module_name = Path(__file__).stem  # Ví dụ "1.1"
result_log_name = f"Result_{current_module_name.replace('.', ',')}.txt"  # Sẽ thành "Result_1,1.txt"
RESULT_LOG_FILE = Path(result_log_name)

# Xoá file log cũ nếu đã tồn tại
if RESULT_LOG_FILE.exists():
    RESULT_LOG_FILE.unlink()

# Lưu hàm print ban đầu
_original_print = print
def print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    message = sep.join(map(str, args)) + end
    _original_print(*args, **kwargs)
    with RESULT_LOG_FILE.open("a", encoding="utf-8") as f:
         f.write(message)

def analyze_show_version(content):
    """
    Phân tích output của câu lệnh 'show version' để lấy thông tin thiết bị.
    
    Hàm này sử dụng regular expressions để trích xuất thông tin từ output của lệnh
    show version của thiết bị Cisco. Nó có thể xử lý ba loại thiết bị chính:
    - IOS XE devices
    - NX-OS devices (Nexus series)
    - IOS devices
    
    Args:
        content (str): Nội dung file chứa output của lệnh show version
        
    Returns:
        dict: Dictionary chứa thông tin về os_type, version và model của thiết bị
        None: Nếu không tìm thấy thông tin hoặc có lỗi xảy ra
    """
    try:
        # IOS XE devices
        if re.search(r'Cisco IOS XE Software', content, flags=re.IGNORECASE):
            os_type = 'IOS XE'
            version_match = re.search(r'Version (\d+\.\d+\.\d+\w*)', content)
            model_match = re.search(r'cisco\s+((?:WS-C|C|ISR)\d+[A-Z0-9-]+)', content, flags=re.IGNORECASE)
            model = model_match.group(1) if model_match else None

        # NX-OS devices
        elif re.search(r'Cisco Nexus Operating System \(NX-OS\)', content, flags=re.IGNORECASE):
            os_type = 'NX-OS'
            version_match = re.search(r'NXOS: version ([^\s]+)', content)
            model_match = re.search(r'cisco Nexus\d+ (C\d+[A-Z0-9-]+)[^\n]*Chassis', content)
            if model_match:
                full_model_line = re.search(r'cisco (Nexus\d+ C\d+[A-Z0-9-]+[^\n]*Chassis)', content)
                model = full_model_line.group(1) if full_model_line else model_match.group(1)
            else:
                model = None

        # IOS devices với dòng chứa "Cisco IOS Software"
        elif re.search(r'Cisco IOS Software', content, flags=re.IGNORECASE):
            os_type = 'IOS'
            version_match = re.search(r'Version ([^\s,]+)', content)
            model_match = re.search(
                r'cisco\s+([^\s\(]+)(?:\s+\((?!revision)[^)]+\))?.*?\(revision',
                content,
                flags=re.IGNORECASE
            )
            model = model_match.group(1) if model_match else None

        # IOS devices dạng switch: "cisco WS-C3750G-24TS-1U (PowerPC405) processor (revision F0)..."
        elif re.search(r'cisco\s+([^\s\(]+).*processor\s+\(revision', content, flags=re.IGNORECASE):
            os_type = 'IOS'
            version_match = re.search(r'Version ([^\s,]+)', content)
            model_match = re.search(
                r'cisco\s+([^\s\(]+)(?:\s+\((?!revision)[^)]+\))?.*?\(revision',
                content,
                flags=re.IGNORECASE
            )
            model = model_match.group(1) if model_match else None

        else:
            return None

        return {
            'os_type': os_type,
            'version': version_match.group(1) if version_match else None,
            'model': model
        }

    except Exception as e:
        print(f"[LỖI] Phân tích show version thất bại: {str(e)}")
        return None

def update_excel_with_com(file_name, os_type, version, model):
    """
    Cập nhật thông tin vào file Excel sử dụng Win32COM.
    
    Hàm này sử dụng Win32COM để tương tác với Excel, giúp bảo toàn các định dạng
    và hình ảnh trong file Excel. Nó tự động tìm file Excel tương ứng dựa trên
    tên file log và cập nhật các ô được chỉ định.
    
    Args:
        file_name (str): Tên file log đang xử lý
        os_type (str): Loại hệ điều hành (IOS, IOS XE, NX-OS)
        version (str): Phiên bản phần mềm
        model (str): Model thiết bị
    """
    try:
        # Xử lý tên file để tìm file Excel tương ứng
        base_name = file_name.split('_')[0] + '_' + file_name.split('_')[1].split('.')[0]
        excel_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Checklist")
        excel_file_path = excel_dir / f"{base_name}.xlsx"
        
        if not excel_file_path.exists():
            print(f"[CẢNH BÁO] File Excel '{base_name}.xlsx' không tồn tại.")
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

            # Chuẩn bị nội dung cần cập nhật
            version_info = f"{os_type} Version {version}" if os_type and version else "Không tìm thấy thông tin Version"

            # Cập nhật các ô trong Excel
            sheet.Range("D8").Value = version_info
            sheet.Range("F11").Value = f"Thiết bị đang sử dụng: {os_type} {version}" if os_type and version else "Thiết bị đang sử dụng: Không tìm thấy thông tin OS/Version"
            sheet.Range("D7").Value = model if model else "Không tìm thấy Model"

            # Lưu và đóng file
            wb.Save()
            wb.Close()
            print(f"[THÔNG BÁO] Đã cập nhật file Excel: {base_name}.xlsx")

        finally:
            # Đảm bảo luôn đóng Excel để tránh treo process
            excel.Quit()

    except Exception as e:
        print(f"[LỖI] Cập nhật Excel thất bại: {str(e)}")

def main():
    """
    Hàm chính điều phối quá trình xử lý file và cập nhật Excel.
    
    Hàm này sẽ:
    1. Quét tất cả file .txt và .log trong thư mục đã định
    2. Đọc và phân tích nội dung từng file
    3. Cập nhật thông tin vào file Excel tương ứng
    """
    # Thư mục chứa file log cần xử lý
    log_dir = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs\parsed_configs\by_command\version")
    
    for file_path in log_dir.glob('*.[tl][xo][tg]'):
        try:
            print(f"\n=== Đang xử lý file: {file_path.name} ===")
            
            # Đọc nội dung file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Phân tích thông tin version
            result = analyze_show_version(content)
            if result:
                print("Kết quả phân tích:")
                print(f"OS Type: {result['os_type']}")
                print(f"Version: {result['version']}")
                print(f"Model: {result['model']}")
                
                # Cập nhật vào file Excel
                update_excel_with_com(
                    file_path.name,
                    result['os_type'],
                    result['version'],
                    result['model']
                )
            else:
                print(f"[CẢNH BÁO] Không tìm thấy thông tin trong file {file_path.name}")

        except Exception as e:
            print(f"[LỖI] Xử lý file {file_path.name} thất bại: {str(e)}")

if __name__ == '__main__':
    main()