import streamlit as st
import gspread
from utils.ncr_helpers import (
    load_ncr_data_with_grouping,
    update_ncr_status,
    REJECT_ESCALATION,
    init_gspread
)

# --- CONFIGURATION ---
DRAFT_STATUS = 'draft'

ROLE_ACTION_STATUSES = {
    'truong_ca': 'cho_truong_ca',
    'truong_bp': 'cho_truong_bp',
    'qc_manager': ['cho_qc_manager', 'xac_nhan_kp_qc_manager'],
    'director': ['cho_giam_doc', 'xac_nhan_kp_director'],
    'bgd_tan_phu': 'cho_bgd_tan_phu'
}

def _get_current_status_from_sheet(so_phieu):
    """
    Đọc trực tiếp trạng thái hiện tại từ Google Sheet để đảm bảo tính nhất quán (Idempotency).
    """
    try:
        gc = init_gspread()
        if not gc: return None
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        data = ws.get_all_values()
        if len(data) < 2: return None
        
        headers = [str(h).strip().lower() for h in data[0]]
        idx_so_phieu = headers.index("so_phieu_ncr")
        idx_status = headers.index("trang_thai")
        
        for row in data[1:]:
            if str(row[idx_so_phieu]).strip() == str(so_phieu).strip():
                return str(row[idx_status]).strip()
        return None
    except Exception:
        return None

@st.cache_data(ttl=60)
def get_pending_approvals(user_role, user_dept, admin_selected_role=None):
    """
    Tải danh sách các phiếu NCR đang chờ phê duyệt dựa trên role và bộ phận.
    """
    effective_role = admin_selected_role if user_role == 'admin' and admin_selected_role else user_role
    filter_status = ROLE_ACTION_STATUSES.get(effective_role)
    
    if not filter_status:
        return None, None, None
        
    needs_dept_filter = effective_role in ['truong_ca', 'truong_bp']
    
    if user_dept == 'all' or user_role == 'admin':
        filter_department = None
    else:
        filter_department = user_dept if needs_dept_filter else None
        
    gc = init_gspread()
    if not gc:
        return None, None, None
        
    df_original, df_grouped = load_ncr_data_with_grouping(
        gc,
        filter_status=filter_status,
        filter_department=filter_department
    )
    
    return df_original, df_grouped, filter_status

def approve_ncr(so_phieu, role, user_name, next_status, solutions=None):
    """
    Thực hiện phê duyệt phiếu NCR với cơ chế kiểm tra trạng thái (Status Guard).
    """
    # Idempotency Check
    current_status = _get_current_status_from_sheet(so_phieu)
    if not current_status:
        return False, "Không tìm thấy phiếu NCR trên hệ thống."
        
    allowed_statuses = ROLE_ACTION_STATUSES.get(role)
    if isinstance(allowed_statuses, list):
        if current_status not in allowed_statuses:
            return False, f"Phiếu đã được xử lý hoặc đang ở trạng thái khác ({current_status})."
    else:
        if current_status != allowed_statuses:
            return False, f"Phiếu đã được xử lý hoặc đang ở trạng thái khác ({current_status})."

    gc = init_gspread()
    if not gc:
        return False, "Không thể kết nối Google Sheets"
        
    solutions = solutions or {}
    
    success, msg = update_ncr_status(
        gc, 
        so_phieu, 
        next_status, 
        user_name, 
        approver_role=role,
        bp_solution=solutions.get('bp_solution'),
        solution=solutions.get('qc_solution'),
        director_solution=solutions.get('director_solution')
    )
    if success:
        st.cache_data.clear()  # Clear cache to refresh data after approval
    return success, msg

def reject_ncr(so_phieu, role, user_name, current_status_ui, reason):
    """
    Từ chối hoặc trả về phiếu NCR với cơ chế kiểm tra trạng thái tương tự Approve.
    """
    # Idempotency Check
    current_status_real = _get_current_status_from_sheet(so_phieu)
    if not current_status_real:
        return False, "Không tìm thấy phiếu NCR."
        
    allowed_statuses = ROLE_ACTION_STATUSES.get(role)
    if isinstance(allowed_statuses, list):
        if current_status_real not in allowed_statuses:
            return False, f"Phiếu đã được xử lý hoặc thay đổi trạng thái ({current_status_real})."
    else:
        if current_status_real != allowed_statuses:
            return False, f"Phiếu đã được xử lý hoặc thay đổi trạng thái ({current_status_real})."

    gc = init_gspread()
    if not gc:
        return False, "Không thể kết nối Google Sheets"
        
    # Lấy đích đến từ REJECT_ESCALATION, dùng hằng số DRAFT_STATUS nếu không có cấu hình
    prev_status = REJECT_ESCALATION.get(current_status_real, DRAFT_STATUS)
    
    success, msg = update_ncr_status(
        gc,
        so_phieu,
        prev_status,
        user_name,
        approver_role=role,
        reject_reason=reason
    )
    if success:
        st.cache_data.clear()  # Clear cache to refresh data after rejection
    return success, msg
