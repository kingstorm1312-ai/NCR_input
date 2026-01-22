import streamlit as st
import pandas as pd
import gspread
import json
import sys
import os
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import (
    load_ncr_data_with_grouping,
    get_status_display_name,
    get_status_color,
    restart_ncr
)

# --- PAGE SETUP ---
st.set_page_config(page_title="QC Giám Sát", page_icon="🔧", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_name = user_info.get("name")
user_role = user_info.get("role")

# Check if user is QC Manager or Director
if user_role not in ['qc_manager', 'director']:
    st.error("❌ Bạn không có quyền truy cập trang này!")
    st.info("Chỉ QC Manager và Giám đốc mới có quyền giám sát")
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def init_gspread():
    """Khởi tạo gspread client từ secrets"""
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        
        if isinstance(creds_str, str):
            credentials_dict = json.loads(creds_str, strict=False)
        else:
            credentials_dict = creds_str
            
        gc = gspread.service_account_from_dict(credentials_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi kết nối System: {e}")
        return None

gc = init_gspread()

# --- HEADER ---
st.title("🔧 QC Giám Sát - Phiếu Bị Từ Chối")
st.caption(f"**{user_name}** ({user_role}) - Quản lý phiếu bị từ chối và escalation")

# Clear cache button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Làm mới", help="Clear cache và tải lại dữ liệu mới nhất"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    # Load all data
    df_all, df_grouped = load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None)

if df_grouped.empty:
    st.info("Chưa có dữ liệu NCR nào trên hệ thống.")
    st.stop()

# --- TABS ---
tab_active, tab_legacy = st.tabs(["🚫 Nhật ký Từ chối (Mới)", "🗄️ Lưu trữ phiếu cũ (Legacy)"])

# ==============================================================================
# TAB 1: NHẬT KÝ TỪ CHỐI (ACTIVE REJECTIONS)
# Logic: Status = 'draft' AND ly_do_tu_choi IS NOT EMPTY
# ==============================================================================
with tab_active:
    st.markdown("### 🔍 Giám sát các phiếu đang bị trả về (Status: Draft)")
    st.caption("Danh sách các phiếu đã bị từ chối và đang nằm ở trạng thái 'Nháp' chờ Staff sửa.")
    
    # Filter Active Rejections
    # Condition: status == 'draft' and ly_do_tu_choi exists and is not empty
    active_rejections = df_grouped[
        (df_grouped['trang_thai'] == 'draft') & 
        (df_grouped['ly_do_tu_choi'].notna()) & 
        (df_grouped['ly_do_tu_choi'] != '')
    ].copy()
    
    if active_rejections.empty:
        st.success("✅ Hiện không có phiếu nào đang bị trả về!")
    else:
        # User requested highlight for Department Manager rejections
        # We can detect this by checking the string format "[Name (TRUONG_BP)]" or similar
        # But generic highlighting for all is safer first.
        
        st.write(f"Tìm thấy **{len(active_rejections)}** phiếu đang bị từ chối.")
        
        # Display as a clean Dataframe/Table for quick scanning
        display_df = active_rejections[[
            'so_phieu', 'nguoi_lap_phieu', 'bo_phan', 'ly_do_tu_choi', 'thoi_gian_cap_nhat'
        ]].copy()
        
        display_df.columns = ['Phiếu', 'Người lập', 'Bộ phận', '⛔ Lý do & Người từ chối', 'Cập nhật']
        
        # Color highlighting function
        def highlight_reason(val):
            val_str = str(val).lower()
            if 'truong_bp' in val_str or 'trưởng bp' in val_str:
                return 'color: #d32f2f; font-weight: bold;' # Red for Dept Manager
            elif 'qc_manager' in val_str or 'qc manager' in val_str:
                return 'color: #7b1fa2; font-weight: bold;' # Purple for QC
            elif 'director' in val_str or 'giam_doc' in val_str:
                return 'color: #c62828; font-weight: bold;' # Dark Red for Director
            return ''

        st.dataframe(
            display_df.style.map(highlight_reason, subset=['⛔ Lý do & Người từ chối']),
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        st.info("💡 **Ghi chú:** Các phiếu này đang ở trạng thái 'Nháp'. Staff cần sửa và gửi lại.")


# ==============================================================================
# TAB 2: LƯU TRỮ PHIẾU CŨ (LEGACY)
# Logic: Status IN ['bi_tu_choi_...']
# ==============================================================================
with tab_legacy:
    st.markdown("### 🗄️ Các phiếu bị từ chối theo quy trình cũ")
    st.warning("⚠️ Đây là các phiếu thuộc quy trình cũ (Dead State). Cần xử lý thủ công nếu muốn khôi phục.")

    # Rejected Statuses
    rejected_statuses = ['bi_tu_choi_truong_ca', 'bi_tu_choi_truong_bp', 'bi_tu_choi_qc_manager', 'bi_tu_choi_giam_doc', 'bi_tu_choi_bgd_tan_phu']
    
    # Filter
    df_rejected_legacy = df_grouped[df_grouped['trang_thai'].isin(rejected_statuses)].copy()
    
    if df_rejected_legacy.empty:
        st.success("✅ Không có phiếu cũ nào!")
    else:
        # Statistics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🚨 Tổng phiếu kẹt", len(df_rejected_legacy))
        
        # Render Ticket Cards
        for _, ticket in df_rejected_legacy.iterrows():
            so_phieu = ticket['so_phieu']
            status = ticket['trang_thai']
            creator = ticket['nguoi_lap_phieu']
            reject_reason = ticket['ly_do_tu_choi']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            last_update = ticket.get('thoi_gian_cap_nhat', '')
            
            with st.container(border=True):
                # Header
                col_title, col_badge = st.columns([3, 1])
                with col_title:
                    st.markdown(f"### 📋 {so_phieu}")
                with col_badge:
                    st.markdown(f":red[{get_status_display_name(status)}]")
                
                # Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                    st.write(f"👤 **Người tạo:** {creator}")
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                with col2:
                    if last_update:
                        st.write(f"🕐 **Cập nhật:** {last_update}")
                
                # Rejection reason
                if reject_reason and str(reject_reason).strip():
                    st.error(f"❌ **Lý do từ chối:** {reject_reason}")
                
                # Actions (Restart/Escalate)
                st.divider()
                st.markdown("#### 🔧 Công cụ Khôi phục (Admin/Manager)")
                
                # Determine restart target
                restart_targets = {
                    'bi_tu_choi_truong_ca': ('cho_truong_ca', 'Trưởng ca'),
                    'bi_tu_choi_truong_bp': ('cho_truong_bp', 'Trưởng BP'),
                    'bi_tu_choi_qc_manager': ('cho_qc_manager', 'QC Manager'),
                    'bi_tu_choi_giam_doc': ('cho_giam_doc', 'Giám đốc'),
                    'bi_tu_choi_bgd_tan_phu': ('cho_bgd_tan_phu', 'BGĐ Tân Phú')
                }
                target_status, target_name = restart_targets.get(status, ('cho_truong_ca', 'Trưởng ca'))
                
                col_restart, col_escalate = st.columns(2)
                
                # RESTART
                with col_restart:
                    restart_note = st.text_input(f"Note restart {so_phieu}", key=f"note_res_{so_phieu}")
                    if st.button(f"🔄 Restart về {target_name}", key=f"btn_res_{so_phieu}"):
                        with st.spinner("Processing..."):
                            success, msg = restart_ncr(gc, so_phieu, target_status, user_name, restart_note)
                            if success:
                                st.success("Done")
                                st.rerun()
                            else:
                                st.error(msg)
                
                # FORCE DRAFT
                with col_escalate:
                    if st.button(f"↩️ Force Restore Draft", key=f"btn_draft_{so_phieu}"):
                        with st.spinner("Processing..."):
                            success, msg = restart_ncr(gc, so_phieu, 'draft', user_name, "Admin Force Restore")
                            if success:
                                st.success("Restored to Draft")
                                st.rerun()
                            else:
                                st.error(msg)


st.divider()
if st.button("🔙 Quay lại Dashboard"):
    st.switch_page("Dashboard.py")
