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
    # Load NCRs with rejection statuses
    rejected_statuses = ['bi_tu_choi_truong_ca', 'bi_tu_choi_truong_bp', 'bi_tu_choi_qc_manager', 'bi_tu_choi_giam_doc']
    df_all, _ = load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None)

# Filter rejected tickets
if not df_all.empty:
    df_rejected = df_all[df_all['trang_thai'].isin(rejected_statuses)].copy()
else:
    df_rejected = pd.DataFrame()

# --- STATISTICS ---
if not df_rejected.empty:
    total_rejected = df_rejected['so_phieu'].nunique()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🚨 Phiếu bị từ chối", total_rejected)
    with col2:
        tbp_rejected = df_rejected[df_rejected['trang_thai'] == 'bi_tu_choi_truong_bp']['so_phieu'].nunique()
        st.metric("👨‍💼 Bị TBP từ chối", tbp_rejected)
    with col3:
        qc_rejected = df_rejected[df_rejected['trang_thai'] == 'bi_tu_choi_qc_manager']['so_phieu'].nunique()
        st.metric("👔 Bị QC từ chối", qc_rejected)
else:
    st.success("✅ Không có phiếu nào bị từ chối!")
    st.stop()

st.divider()

# --- REJECTED TICKETS TABLE ---
st.subheader("📋 Danh sách phiếu bị từ chối")

# Group by ticket
tickets_rejected = df_rejected.groupby(['so_phieu', 'trang_thai']).agg({
    'ngay_lap': 'first',
    'sl_loi': 'sum',
    'nguoi_lap_phieu': 'first',
    'ly_do_tu_choi': 'first',
    'thoi_gian_cap_nhat': 'first'
}).reset_index()

for _, ticket in tickets_rejected.iterrows():
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
        
        # Error details
        with st.expander("🔍 Chi tiết lỗi"):
            ticket_rows = df_rejected[df_rejected['so_phieu'] == so_phieu]
            if not ticket_rows.empty:
                display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'muc_do']
                available_cols = [col for col in display_cols if col in ticket_rows.columns]
                st.dataframe(
                    ticket_rows[available_cols],
                    use_container_width=True,
                    hide_index=True
                )
        
        st.write("---")
        st.markdown("### 🎯 Hành động")
        
        # Determine restart target based on rejection level
        restart_targets = {
            'bi_tu_choi_truong_ca': ('cho_truong_ca', 'Trưởng ca'),
            'bi_tu_choi_truong_bp': ('cho_truong_bp', 'Trưởng BP'),
            'bi_tu_choi_qc_manager': ('cho_qc_manager', 'QC Manager'),
            'bi_tu_choi_giam_doc': ('cho_giam_doc', 'Giám đốc')
        }
        
        target_status, target_name = restart_targets.get(status, ('cho_truong_ca', 'Trưởng ca'))
        
        # 3 columns for 3 actions
        col_restart, col_escalate, col_return_staff = st.columns(3)
        
        # ACTION 1: RESTART
        with col_restart:
            restart_note = st.text_area(
                f"Ghi chú cho {target_name}:",
                key=f"restart_note_{so_phieu}",
                placeholder="Nhập ghi chú...",
                height=80
            )
            
            if st.button(
                f"🔄 RESTART → {target_name}",
                key=f"restart_{so_phieu}",
                type="primary",
                use_container_width=True,
                help=f"Gửi lại phiếu về {target_name} để xem xét lại"
            ):
                with st.spinner("Đang xử lý..."):
                    success, message = restart_ncr(gc, so_phieu, target_status, user_name, restart_note)
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # ACTION 2: ESCALATE
        with col_escalate:
            # Escalate to next higher level
            escalate_targets = {
                'bi_tu_choi_truong_ca': ('cho_truong_bp', 'Trưởng BP'),
                'bi_tu_choi_truong_bp': ('cho_giam_doc', 'Giám đốc'),  # Skip QC, go to Director
                'bi_tu_choi_qc_manager': ('cho_giam_doc', 'Giám đốc'),
                'bi_tu_choi_giam_doc': None  # No escalation for Director reject
            }
            
            escalate_info = escalate_targets.get(status)
            
            if escalate_info:
                escalate_status, escalate_name = escalate_info
                
                escalate_note = st.text_area(
                    f"Ghi chú cho {escalate_name}:",
                    key=f"escalate_note_{so_phieu}",
                    placeholder="Nhập ghi chú...",
                    height=80
                )
                
                # Custom label for bi_tu_choi_truong_bp
                if status == 'bi_tu_choi_truong_bp':
                    button_label = "📤 GỬI CHO DIRECTOR"
                else:
                    button_label = f"⬆️ ESCALATE → {escalate_name}"
                
                if st.button(
                    button_label,
                    key=f"escalate_{so_phieu}",
                    use_container_width=True,
                    help=f"Chuyển phiếu lên {escalate_name} để xem xét"
                ):
                    with st.spinner("Đang xử lý..."):
                        full_note = f"[QC Manager escalate] {escalate_note}" if escalate_note else "Escalated by QC Manager"
                        success, message = restart_ncr(gc, so_phieu, escalate_status, user_name, full_note)
                        
                        if success:
                            st.success(f"✅ Đã gửi lên {escalate_name}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
            else:
                st.text_area("Ghi chú:", disabled=True, height=80, key=f"esc_disabled_{so_phieu}")
                st.info("🔚 Final rejection")
        
        # ACTION 3: RETURN TO STAFF
        with col_return_staff:
            return_note = st.text_area(
                "Lý do trả về Staff:",
                key=f"return_note_{so_phieu}",
                placeholder="Nhập lý do...",
                height=80
            )
            
            if st.button(
                "↩️ TRẢ VỀ STAFF",
                key=f"return_staff_{so_phieu}",
                use_container_width=True,
                help="Trả phiếu về Staff để sửa lại"
            ):
                if not return_note.strip():
                    st.error("⚠️ Vui lòng nhập lý do trả về!")
                else:
                    with st.spinner("Đang xử lý..."):
                        # Return to draft with note
                        full_note = f"[QC Manager] {return_note}"
                        success, message = restart_ncr(gc, so_phieu, 'draft', user_name, full_note)
                        
                        if success:
                            st.success(f"✅ Đã trả phiếu về Staff")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

# --- FOOTER ---
st.divider()
if st.button("🔙 Quay lại Dashboard"):
    st.switch_page("Dashboard.py")
