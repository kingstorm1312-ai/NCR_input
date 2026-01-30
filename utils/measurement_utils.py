import random
import re

def parse_tolerance(tol_str):
    """
    Trích xuất giá trị dung sai từ chuỗi.
    Hỗ trợ: "+/- 1", "±1", "1", "0.5", "5%"
    Trả về: float value (absolute)
    """
    if not tol_str:
        return 0.0
        
    # Xử lý phần trăm (chưa implement ngữ cảnh lấy theo spec, tạm thời lấy số)
    # clean string
    clean = tol_str.replace("±", "").replace("+/-", "").replace("+", "").replace("-", "").strip()
    
    # Tìm số đầu tiên
    match = re.search(r"(\d+(\.\d+)?)", clean)
    if match:
        try:
            return float(match.group(1))
        except:
            return 0.0
    return 0.0

def generate_random_measurement(spec_str, tol_str):
    """
    Tạo số liệu đo đạc ngẫu nhiên dựa trên Spec và Tolerance.
    - Giữ nguyên format của spec (VD: "20x30" -> "20.1x30.2")
    - Random trong khoảng +/- tol/2 (hoặc tol tùy định nghĩa user, ở đây giả sử tol là full range hoặc +/- value). 
      Thường "+/- 1" nghĩa là range từ -1 đến +1.
    """
    if not spec_str:
        return ""
        
    tol_val = parse_tolerance(tol_str)
    if tol_val == 0:
        return spec_str
        
    # Hàm tìm và thay thế số trong chuỗi spec
    def replace_num(match):
        base_val = float(match.group(1))
        # Random deviation: uniform between -tol and +tol
        # Giả định tol_str là "+/- X" thì dev là [-X, X]
        # Nếu muốn an toàn hơn (trong vùng xanh): lấy +/- 80% của tol
        safe_factor = 0.9 
        deviation = random.uniform(-tol_val * safe_factor, tol_val * safe_factor)
        
        new_val = base_val + deviation
        
        # Determine decimals from input or default to 1-2
        if "." in match.group(1):
            decimals = len(match.group(1).split(".")[1])
        else:
            decimals = 1 if isinstance(new_val, float) else 0
            # Nếu tol nhỏ (0.x) thì nên có decimal
            if tol_val < 1: decimals = max(decimals, 2)
            
        return f"{new_val:.{decimals}f}"

    # Regex tìm tất cả số (int hoặc float)
    # Pattern: số có dấu chấm hoặc không
    result = re.sub(r"(\d+(\.\d+)?)", replace_num, spec_str)
    return result
