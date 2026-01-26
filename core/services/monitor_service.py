import pandas as pd
import streamlit as st
from utils.ncr_helpers import (
    init_gspread,
    load_ncr_data_with_grouping,
    restart_ncr
)

@st.cache_data(ttl=300)
def get_monitor_data():
    """
    Tải tất cả dữ liệu NCR và trả về dưới dạng grouped dataframe.
    """
    # Load all data (no filters at load time)
    df_all, df_grouped = load_ncr_data_with_grouping(filter_status=None, filter_department=None)
    return df_grouped

def prepare_active_rejections(df):
    """
    Lọc danh sách các phiếu đang bị trả về (Status: Draft và có lý do từ chối).
    """
    if df.empty:
        return pd.DataFrame()
        
    active_rejections = df[
        (df['trang_thai'] == 'draft') & 
        (df['ly_do_tu_choi'].notna()) & 
        (df['ly_do_tu_choi'] != '')
    ].copy()
    
    if not active_rejections.empty:
        # Đảm bảo có cột bo_phan
        if 'bo_phan' not in active_rejections.columns:
            def extract_dept_simple(so_phieu):
                parts = str(so_phieu).split('-')
                if len(parts) >= 2:
                    return '-'.join(parts[:2])
                return parts[0] if parts else ''
            active_rejections['bo_phan'] = active_rejections['so_phieu'].apply(extract_dept_simple)
            
        # Đảm bảo các cột tùy chọn tồn tại
        for col in ['ly_do_tu_choi', 'thoi_gian_cap_nhat']:
            if col not in active_rejections.columns:
                active_rejections[col] = ''
                
    return active_rejections

def prepare_legacy_rejections(df):
    """
    Lọc danh sách các phiếu bị từ chối theo quy trình cũ (Legacy).
    """
    if df.empty:
        return pd.DataFrame()
        
    rejected_statuses = [
        'bi_tu_choi_truong_ca', 
        'bi_tu_choi_truong_bp', 
        'bi_tu_choi_qc_manager', 
        'bi_tu_choi_giam_doc', 
        'bi_tu_choi_bgd_tan_phu'
    ]
    
    df_rejected_legacy = df[df['trang_thai'].isin(rejected_statuses)].copy()
    return df_rejected_legacy

def perform_restart_ncr(so_phieu, target_status, user_name, note):
    """
    Thực hiện restart/khôi phục phiếu NCR.
    """
    gc = init_gspread()
    if not gc:
        return False, "Không thể kết nối Google Sheets"
    return restart_ncr(gc, so_phieu, target_status, user_name, note)
