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
    update_ncr_status,
    get_status_display_name,
    get_status_color,
    ROLE_TO_STATUS
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Phê Duyệt NCR", page_icon="✍️", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_role = user_info.get("role")
user_name = user_info.get("name")
user_dept = user_info.get("department")

# --- ROLE CHECK ---
allowed_roles = ['truong_ca', 'truong_bp', 'qc_manager', 'director', 'admin']
if user_role not in allowed_roles:
    st.error(f"⛔ Role '{user_role}' không có quyền phê duyệt!")
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
st.title("✍️ Phê Duyệt NCR")
st.caption(f"Xin chào **{user_name}** - Role: **{user_role.upper()}**")
st.divider()

# --- DETERMINE FILTER BASED ON ROLE ---
# Admin can act as any role
if user_role == 'admin':
    st.info("🔑 Admin Mode: Chọn role để xem NCR cần phê duyệt")
    selected_role = st.selectbox(
        "Xem với quyền:",
        ['truong_ca', 'truong_bp', 'qc_manager', 'director']
    )
    filter_status = ROLE_TO_STATUS[selected_role]
else:
    selected_role = user_role
    filter_status = ROLE_TO_STATUS.get(user_role)

if not filter_status:
    st.error("Role không hợp lệ!")
    st.stop()

# Determine if we need department filter
needs_dept_filter = selected_role in ['truong_ca', 'truong_bp']
filter_department = user_dept if needs_dept_filter else None

# DEBUG OUTPUT (TEMPORARY)
st.write("🔧 **DEBUG INFO:**")
st.json({
    "user_name": user_name,
    "user_role": user_role,
    "user_dept": user_dept,
    "selected_role": selected_role,
    "filter_status": filter_status,
    "needs_dept_filter": needs_dept_filter,
    "filter_department": filter_department
})
st.divider()

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    df_original, df_grouped = load_ncr_data_with_grouping(
        gc,
        filter_status=filter_status,
        filter_department=filter_department
    )

# --- DISPLAY STATUS INFO ---
col_info1, col_info2 = st.columns(2)
with col_info1:
    st.metric("Đang xem trạng thái", get_status_display_name(filter_status))
with col_info2:
    st.metric("Số phiếu cần phê duyệt", len(df_grouped) if not df_grouped.empty else 0)

st.divider()

# --- RENDER APPROVAL CARDS ---
if df_grouped.empty:
    st.success("✅ Không có phiếu NCR nào cần phê duyệt!")
else:
    st.subheader("📋 Danh sách phiếu NCR")
    
    # Iterate through each ticket
    for idx, row in df_grouped.iterrows():
        so_phieu = row['so_phieu']
        ngay_lap = row['ngay_lap']
        nguoi_lap = row['nguoi_lap_phieu']
        tong_loi = row['sl_loi']
        danh_sach_loi = row['ten_loi']
        trang_thai = row['trang_thai']
        
        # Create card container
        with st.container(border=True):
            # Header row
            col_ticket, col_status = st.columns([3, 1])
            with col_ticket:
                st.markdown(f"### 📋 {so_phieu}")
            with col_status:
                status_color = get_status_color(trang_thai)
                st.markdown(f":{status_color}[{get_status_display_name(trang_thai)}]")
            
            # Info grid
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"👤 **Người lập:** {nguoi_lap}")
                st.write(f"📅 **Ngày tạo:** {ngay_lap}")
            with col2:
                st.write(f"⚠️ **Tổng lỗi:** {tong_loi}")
                if 'bo_phan' in row:
                    st.write(f"🏢 **Bộ phận:** {row['bo_phan'].upper()}")
            
            # Error details in expander
            with st.expander("🔍 Chi tiết lỗi"):
                # Get original rows for this ticket
                ticket_rows = df_original[df_original['so_phieu'] == so_phieu]
                if not ticket_rows.empty:
                    display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'muc_do']
                    available_cols = [col for col in display_cols if col in ticket_rows.columns]
                    st.dataframe(
                        ticket_rows[available_cols],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.write(danh_sach_loi)
            
            # --- ACTION SECTION ---
            st.write("")  # Spacer
            
            # QC Manager needs to input solution
            if selected_role == 'qc_manager':
                solution = st.text_area(
                    "💡 Hướng giải quyết (BẮT BUỘC)",
                    key=f"solution_{so_phieu}",
                    placeholder="Nhập hướng xử lý..."
                )
            else:
                solution = None
            
            # Action buttons
            col_approve, col_reject = st.columns(2)
            
            with col_approve:
                if st.button(
                    "✅ PHÊ DUYỆT",
                    key=f"approve_{so_phieu}",
                    type="primary",
                    use_container_width=True
                ):
                    # Validate QC Manager solution
                    if selected_role == 'qc_manager' and (not solution or solution.strip() == ''):
                        st.error("⚠️ Vui lòng nhập hướng giải quyết trước khi phê duyệt!")
                    else:
                        with st.spinner("Đang xử lý..."):
                            success, message = update_ncr_status(
                                gc=gc,
                                so_phieu=so_phieu,
                                action='approve',
                                user_name=user_name,
                                user_role=selected_role,
                                solution=solution
                            )
                            
                            if success:
                                st.success(f"✅ {message}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
            
            with col_reject:
                if st.button(
                    "❌ TỪ CHỐI",
                    key=f"reject_btn_{so_phieu}",
                    use_container_width=True
                ):
                    st.session_state[f'show_reject_{so_phieu}'] = True
            
            # Reject reason input (conditional)
            if st.session_state.get(f'show_reject_{so_phieu}', False):
                reject_reason = st.text_area(
                    "Lý do từ chối:",
                    key=f"reject_reason_{so_phieu}",
                    placeholder="Nhập lý do..."
                )
                
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Xác nhận từ chối", key=f"confirm_reject_{so_phieu}", type="secondary"):
                        if not reject_reason or reject_reason.strip() == '':
                            st.warning("Vui lòng nhập lý do từ chối!")
                        else:
                            with st.spinner("Đang xử lý..."):
                                success, message = update_ncr_status(
                                    gc=gc,
                                    so_phieu=so_phieu,
                                    action='reject',
                                    user_name=user_name,
                                    user_role=selected_role,
                                    reject_reason=reject_reason
                                )
                                
                                if success:
                                    st.warning(f"❌ {message}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                
                with col_cancel:
                    if st.button("Hủy", key=f"cancel_reject_{so_phieu}"):
                        st.session_state[f'show_reject_{so_phieu}'] = False
                        st.rerun()
        
        st.write("")  # Spacer between cards

# --- FOOTER ---
st.divider()
if st.button("🔙 Quay lại Dashboard"):
    st.switch_page("Dashboard.py")
