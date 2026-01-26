import streamlit as st
from utils.ncr_helpers import (
    load_ncr_data_with_grouping,
    update_ncr_status,
    REJECT_ESCALATION,
    init_gspread
)

# --- CONFIGURATION ---
ROLE_ACTION_STATUSES = {
    'truong_ca': 'cho_truong_ca',
    'truong_bp': 'cho_truong_bp',
    'qc_manager': ['cho_qc_manager', 'xac_nhan_kp_qc_manager'],
    'director': ['cho_giam_doc', 'xac_nhan_kp_director'],
    'bgd_tan_phu': 'cho_bgd_tan_phu'
}

def get_pending_approvals(user_role, user_dept, admin_selected_role=None):
    """
    Tải danh sách các phiếu NCR đang chờ phê duyệt dựa trên role và bộ phận.
    """
    # Xác định role thực tế để lọc (Admin có thể giả lập role khác)
    effective_role = admin_selected_role if user_role == 'admin' and admin_selected_role else user_role
    filter_status = ROLE_ACTION_STATUSES.get(effective_role)
    
    if not filter_status:
        return None, None, None # Invalid role
        
    # Xác định có cần lọc theo bộ phận không
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
    Thực hiện phê duyệt phiếu NCR.
    solutions: dict chứa các biện pháp/hướng giải quyết tùy theo role.
    """
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
    return success, msg

def reject_ncr(so_phieu, role, user_name, current_status, reason):
    """
    Từ chối hoặc trả về phiếu NCR.
    """
    gc = init_gspread()
    if not gc:
        return False, "Không thể kết nối Google Sheets"
        
    prev_status = REJECT_ESCALATION.get(current_status, 'draft')
    
    success, msg = update_ncr_status(
        gc,
        so_phieu,
        prev_status,
        user_name,
        approver_role=role,
        reject_reason=reason
    )
    return success, msg
