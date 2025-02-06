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

# --- Constants ---
SYSTEM_VLANS = {'1002', '1003', '1004', '1005'}
PORT_PREFIXES = ('Gi', 'Fa', 'Te', 'Eth', 'Po')

class VlanViolations:
    """Class để lưu trữ các vi phạm VLAN."""
    def __init__(self):
        self.access_ports_vlan1 = set()
        self.trunk_native_vlan1 = set()
        self.trunk_allow_vlan1 = set()
        self.trunk_allow_vlan_all = set()

    def has_violations(self):
        """Kiểm tra xem có vi phạm nào không."""
        return any([
            self.access_ports_vlan1,
            self.trunk_native_vlan1,
            self.trunk_allow_vlan1,
            self.trunk_allow_vlan_all
        ])

    def get_violations_text(self):
        """Tạo text mô tả vi phạm."""
        result_parts = []
        
        if self.access_ports_vlan1:
            result_parts.append("Access Ports sử dụng VLAN 1:")
            result_parts.extend(f"- {port}" for port in sorted(self.access_ports_vlan1))
        
        if self.trunk_native_vlan1:
            if result_parts:
                result_parts.append("")
            result_parts.append("Trunk Ports có native VLAN 1:")
            result_parts.extend(f"- {port}" for port in sorted(self.trunk_native_vlan1))
        
        if self.trunk_allow_vlan1:
            if result_parts:
                result_parts.append("")
            result_parts.append("Trunk Ports cho phép VLAN 1:")
            result_parts.extend(f"- {port}" for port in sorted(self.trunk_allow_vlan1))
            
        return "\n".join(result_parts)

    def get_recommendations(self):
        """Tạo danh sách đề xuất dựa trên vi phạm."""
        recommendations = []
        if self.access_ports_vlan1:
            recommendations.append("- Cấu hình VLAN mới cho các Access Ports đang sử dụng VLAN 1")
        if self.trunk_native_vlan1:
            recommendations.append("- Thay đổi native VLAN trên các Trunk Ports khỏi VLAN 1")
        if self.trunk_allow_vlan1 or self.trunk_allow_vlan_all:
            recommendations.append("- Cấu hình allowed VLANs cụ thể trên các Trunk Ports, loại bỏ VLAN 1 và không sử dụng 'all'")
        return "\n".join(recommendations)

def parse_show_vlan(vlan_output):
    """Phân tích output của lệnh show vlan."""
    vlan_dict = {}
    current_vlan = None
    
    for line in vlan_output.splitlines():
        line = line.strip()
        if not line or line.startswith('VLAN') or line.startswith('----'):
            continue
            
        match = re.match(r'(\d+)\s+(\S+)\s+\S+\s*(.*)', line)
        if match:
            vlan_id, vlan_name, ports = match.groups()
            
            if vlan_id in SYSTEM_VLANS:
                continue
                
            current_vlan = vlan_id
            valid_ports = [p.strip() for p in ports.split(',') 
                         if p.strip() and any(p.strip().startswith(prefix) 
                         for prefix in PORT_PREFIXES)]
            vlan_dict[vlan_id] = valid_ports
        elif current_vlan and current_vlan not in SYSTEM_VLANS:
            additional_ports = [p.strip() for p in line.split(',') 
                              if p.strip() and any(p.strip().startswith(prefix) 
                              for prefix in PORT_PREFIXES)]
            if additional_ports:
                vlan_dict.setdefault(current_vlan, []).extend(additional_ports)
    
    return vlan_dict

def parse_show_interface_trunk(trunk_output):
    """Phân tích output của lệnh show interface trunk."""
    trunk_dict = {}
    
    sections = re.split(r'\n\n+', trunk_output)
    
    for section in sections:
        lines = section.splitlines()
        if any(line.strip().startswith(('Port', 'Name')) for line in lines):
            for line in lines:
                line = line.strip()
                if not line or line.startswith(('Port', '----')):
                    continue
                
                if not any(line.startswith(prefix) for prefix in PORT_PREFIXES):
                    continue
                
                fields = line.split()
                if len(fields) >= 5:
                    port = fields[0]
                    if port.startswith(PORT_PREFIXES):
                        trunk_dict[port] = {
                            'mode': fields[1].lower() if len(fields) > 1 else '',
                            'encapsulation': fields[2] if len(fields) > 2 else '',
                            'status': fields[3].lower() if len(fields) > 3 else '',
                            'native_vlan': fields[4] if len(fields) > 4 else '',
                            'allowed_vlans': 'all'
                        }
    
    # Parse allowed VLANs
    allowed_section = next((section for section in sections 
                          if 'allowed vlan' in section.lower()), None)
    
    if allowed_section:
        for line in allowed_section.splitlines():
            line = line.strip()
            if any(line.startswith(prefix) for prefix in PORT_PREFIXES):
                fields = line.split()
                if len(fields) >= 2:
                    port = fields[0]
                    vlan_part = ' '.join(fields[1:])
                    vlan_match = re.search(r'(?:allowed\s+vlan[s]?\s*:?\s*)([\d,-]+|all)', 
                                         vlan_part, re.IGNORECASE)
                    if vlan_match and port in trunk_dict:
                        trunk_dict[port]['allowed_vlans'] = vlan_match.group(1)
    
    return trunk_dict

def check_vlan_violations(config_content):
    """Kiểm tra vi phạm VLAN trong nội dung cấu hình."""
    try:
        show_vlan_pattern = r'show vlan\s*\n(.*?)(?=\n\S+#|\Z)'
        show_trunk_pattern = r'show interface trunk\s*\n(.*?)(?=\n\S+#|\Z)'
        
        # Tìm phần show vlan và show interface trunk
        show_vlan_match = re.search(show_vlan_pattern, config_content, re.DOTALL)
        show_trunk_match = re.search(show_trunk_pattern, config_content, re.DOTALL)
        
        if not show_vlan_match or not show_trunk_match:
            print("[CẢNH BÁO] Không tìm thấy output của lệnh show vlan hoặc show interface trunk")
            return None
            
        vlan_info = parse_show_vlan(show_vlan_match.group(1))
        trunk_info = parse_show_interface_trunk(show_trunk_match.group(1))
        
        violations = VlanViolations()
        
        # Kiểm tra VLAN 1
        for port in vlan_info.get('1', []):
            if port in trunk_info:
                trunk_config = trunk_info[port]
                if trunk_config['native_vlan'] == '1':
                    violations.trunk_native_vlan1.add(port)
                allowed_vlans = trunk_config['allowed_vlans'].lower()
                if '1' in allowed_vlans.split(',') or 'all' in allowed_vlans:
                    violations.trunk_allow_vlan1.add(port)
                if 'all' in allowed_vlans:
                    violations.trunk_allow_vlan_all.add(port)
            else:
                violations.access_ports_vlan1.add(port)
        
        # Kiểm tra thêm các trunk ports
        for port, info in trunk_info.items():
            if info['native_vlan'] == '1':
                violations.trunk_native_vlan1.add(port)
            allowed_vlans = info['allowed_vlans'].lower()
            if '1' in allowed_vlans.split(',') or 'all' in allowed_vlans:
                violations.trunk_allow_vlan1.add(port)
            if 'all' in allowed_vlans:
                violations.trunk_allow_vlan_all.add(port)
        
        return violations
        
    except Exception as e:
        print(f"[LỖI] Kiểm tra vi phạm VLAN thất bại: {str(e)}")
        return None

def update_excel_with_com(file_name, violations):
    """Cập nhật kết quả vào file Excel sử dụng Win32COM."""
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
        excel.Visible = False
        
        try:
            # Mở workbook và lấy sheet active
            wb = excel.Workbooks.Open(abs_path)
            sheet = wb.ActiveSheet

            # Cập nhật Excel dựa trên kết quả kiểm tra
            if violations and violations.has_violations():
                # Không tuân thủ - có vi phạm
                sheet.Range("F15").Value = violations.get_violations_text()
                sheet.Range("G15").Value = violations.get_recommendations()
                sheet.Range("E15").Value = sheet.Range("E5").Value  # Không tuân thủ
            else:
                # Tuân thủ - không có vi phạm
                sheet.Range("F15").Value = "Không phát hiện cổng nào sử dụng VLAN mặc định"
                sheet.Range("G15").Value = "Không"
                sheet.Range("E15").Value = sheet.Range("E4").Value  # Tuân thủ
                sheet.Range("H15").Value = sheet.Range("H7").Value

            # Lưu và đóng file
            wb.Save()
            wb.Close()
            print(f"[THÔNG BÁO] Đã cập nhật file Excel: {excel_file_path.name}")

        finally:
            excel.Quit()

    except Exception as e:
        print(f"[LỖI] Cập nhật Excel thất bại: {str(e)}")

def main():
    """Hàm chính của chương trình."""
    try:
        log_folder_path = Path(r"C:\Users\vantu\Desktop\Root\TEST\Configs")
        
        print("\n=== Bắt đầu kiểm tra vi phạm VLAN ===")
        
        for log_file in log_folder_path.glob("*.[lt][xo][tg]"):
            try:
                print(f"\n--- Đang xử lý file: {log_file.name} ---")
                
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                violations = check_vlan_violations(content)
                
                if violations:
                    print("Kết quả phân tích:")
                    if violations.has_violations():
                        print(violations.get_violations_text())
                        print("\nĐề xuất:")
                        print(violations.get_recommendations())
                    else:
                        print("Không phát hiện vi phạm VLAN")
                    
                    update_excel_with_com(log_file.name, violations)
                else:
                    print(f"[CẢNH BÁO] Không tìm thấy thông tin VLAN trong file {log_file.name}")
                    
            except Exception as e:
                print(f"[LỖI] Xử lý file {log_file.name} thất bại: {str(e)}")
                continue
                
    except Exception as e:
        print(f"[LỖI] Lỗi chung trong quá trình xử lý: {str(e)}")

if __name__ == "__main__":
    main()