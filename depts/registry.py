from depts.fi import PROFILE as FI_PROFILE
from depts.may_i import PROFILE as MAYI_PROFILE
from depts.may_p2 import PROFILE as MAYP2_PROFILE
from core.profile import DeptProfile

# Registry chứa tất cả các profiles bộ phận
DEPTS = {
    "fi": FI_PROFILE,
    "may_i": MAYI_PROFILE,
    "may_p2": MAYP2_PROFILE
}

def get_dept(code: str) -> DeptProfile:
    """
    Truy xuất profile của bộ phận dựa trên mã code.
    """
    if code not in DEPTS:
        raise KeyError(f"Registry Error: Không tìm thấy profile cho bộ phận code='{code}'. Các code hợp lệ: {list(DEPTS.keys())}")
    return DEPTS[code]
