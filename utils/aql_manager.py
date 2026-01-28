
def get_aql_standard(lot_size):
    """
    Trả về tiêu chuẩn AQL (Level II, Major 2.5, Minor 4.0) dựa trên số lượng lô hàng.
    Input: lot_size (int)
    Output: dict {
        'code': Mã chữ,
        'sample_size': Cỡ mẫu,
        'ac_major': Ac lỗi nặng,
        're_major': Re lỗi nặng (thực tế là ac + 1),
        'ac_minor': Ac lỗi nhẹ,
        're_minor': Re lỗi nhẹ
    }
    """
    try:
        ls = int(lot_size)
    except:
        return None

    if ls <= 0: return None
    
    # Lookup Table
    if ls <= 8:
        return {'code': 'A', 'sample_size': 2, 'ac_major': 0, 'ac_minor': 0}
    elif ls <= 15:
        return {'code': 'B', 'sample_size': 3, 'ac_major': 0, 'ac_minor': 0}
    elif ls <= 25:
        return {'code': 'C', 'sample_size': 5, 'ac_major': 0, 'ac_minor': 0}
    elif ls <= 50:
        return {'code': 'D', 'sample_size': 8, 'ac_major': 0, 'ac_minor': 1}
    elif ls <= 90:
        return {'code': 'E', 'sample_size': 13, 'ac_major': 1, 'ac_minor': 1}
    elif ls <= 150:
        return {'code': 'F', 'sample_size': 20, 'ac_major': 1, 'ac_minor': 2}
    elif ls <= 280:
        return {'code': 'G', 'sample_size': 32, 'ac_major': 2, 'ac_minor': 3}
    elif ls <= 500:
        return {'code': 'H', 'sample_size': 50, 'ac_major': 3, 'ac_minor': 5}
    elif ls <= 1200:
        return {'code': 'J', 'sample_size': 80, 'ac_major': 5, 'ac_minor': 7}
    elif ls <= 3200:
        return {'code': 'K', 'sample_size': 125, 'ac_major': 7, 'ac_minor': 10}
    elif ls <= 10000:
        return {'code': 'L', 'sample_size': 200, 'ac_major': 10, 'ac_minor': 14}
    elif ls <= 35000:
        return {'code': 'M', 'sample_size': 315, 'ac_major': 14, 'ac_minor': 21}
    elif ls <= 150000:
        return {'code': 'N', 'sample_size': 500, 'ac_major': 21, 'ac_minor': 21}
    elif ls <= 500000:
        return {'code': 'P', 'sample_size': 800, 'ac_major': 21, 'ac_minor': 21}
    else: # > 500,000
        return {'code': 'Q', 'sample_size': 1250, 'ac_major': 21, 'ac_minor': 21}

def evaluate_lot_quality(lot_size, total_major, total_minor, custom_limits=None):
    """
    Đánh giá kết quả kiểm tra lô hàng.
    Input: 
        lot_size: Số lượng lô
        total_major: Tổng lỗi nặng
        total_minor: Tổng lỗi nhẹ
        custom_limits: dict {'ac_major': int, 'ac_minor': int} (Optional)
    Output:
        status: 'Pass' | 'Fail'
        details: dict (std, effective_limits, pass_major, pass_minor)
    """
    std = get_aql_standard(lot_size)
    
    # Determine limits
    if custom_limits:
        limit_major = custom_limits.get('ac_major', 0)
        limit_minor = custom_limits.get('ac_minor', 0)
    elif std:
        limit_major = std['ac_major']
        limit_minor = std['ac_minor']
    else:
        return 'N/A', {}
    
    # Check Major
    pass_major = total_major <= limit_major
    
    # Check Minor
    pass_minor = total_minor <= limit_minor
    
    is_pass = pass_major and pass_minor
    
    return 'Pass' if is_pass else 'Fail', {
        'standard': std,
        'effective_limits': {'ac_major': limit_major, 'ac_minor': limit_minor},
        'pass_major': pass_major,
        'pass_minor': pass_minor
    }
