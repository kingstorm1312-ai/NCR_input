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
    get_status_color
)

# --- PAGE SETUP ---
st.set_page_config(page_title="NCR Của Tôi", page_icon="🙋", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_name = user_info.get("name")

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
st.title("🙋 NCR Của Tôi")
st.caption(f"Xin chào **{user_name}** - Quản lý các phiếu NCR bạn đã tạo")
st.divider()

# --- HELPER: RESUBMIT FUNCTION ---
def resubmit_ncr(so_phieu):
    """Gửi lại phiếu NCR (reset status về cho_truong_ca)"""
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        all_data = ws.get_all_values()
        headers = all_data[0]
        
        # Map column names
        from utils.ncr_helpers import COLUMN_MAPPING
        col_so_phieu = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
        col_trang_thai = headers.index(COLUMN_MAPPING.get('trang_thai', 'trang_thai'))
        col_thoi_gian = headers.index(COLUMN_MAPPING.get('thoi_gian_cap_nhat', 'thoi_gian_cap_nhat'))
        
        # Find rows to update
        rows_to_update = []
        for idx, row in enumerate(all_data[1:], start=2):
            if row[col_so_phieu] == so_phieu:
                rows_to_update.append(idx)
        
        if not rows_to_update:
            return False, "Không tìm thấy phiếu"
        
        # Update status and timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = []
        
        for row_idx in rows_to_update:
            updates.append({
                'range': f'{chr(65 + col_trang_thai)}{row_idx}',
                'values': [['cho_truong_ca']]
            })
            updates.append({
                'range': f'{chr(65 + col_thoi_gian)}{row_idx}',
                'values': [[current_time]]
            })
        
        ws.batch_update(updates)
        return True, f"Đã gửi lại phiếu {so_phieu} ({len(rows_to_update)} dòng)"
        
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    # Load all NCR data (no status filter)
    df_all, _ = load_ncr_data_with_grouping(gc, filter_status=None, filter_department=None)

# Filter by creator
if not df_all.empty:
    df_my_ncrs = df_all[df_all['nguoi_lap_phieu'] == user_name].copy()
else:
    df_my_ncrs = pd.DataFrame()

# --- STATISTICS ---
if not df_my_ncrs.empty:
    total_tickets = df_my_ncrs['so_phieu'].nunique()
    total_errors = df_my_ncrs['sl_loi'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Tổng số phiếu", total_tickets)
    with col2:
        st.metric("⚠️ Tổng số lỗi", int(total_errors))
    with col3:
        draft_count = df_my_ncrs[df_my_ncrs['trang_thai'] == 'draft']['so_phieu'].nunique()
        st.metric("🔴 Cần xử lý", draft_count)
else:
    st.info("ℹ️ Bạn chưa tạo phiếu NCR nào")
    st.stop()

st.divider()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🔴 Cần xử lý", "⏳ Đang chờ duyệt", "✅ Hoàn thành"])

# --- TAB 1: DRAFT/REJECTED ---
with tab1:
    st.subheader("📋 Phiếu cần xử lý (Draft)")
    
    df_draft = df_my_ncrs[df_my_ncrs['trang_thai'] == 'draft']
    
    if df_draft.empty:
        st.success("✅ Không có phiếu nào cần xử lý!")
    else:
        # Group by ticket
        tickets_draft = df_draft.groupby('so_phieu').agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'ly_do_tu_choi': 'first',
            'trang_thai': 'first'
        }).reset_index()
        
        for _, ticket in tickets_draft.iterrows():
            so_phieu = ticket['so_phieu']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            ly_do = ticket['ly_do_tu_choi']
            
            with st.container(border=True):
                # Header
                col_title, col_badge = st.columns([3, 1])
                with col_title:
                    st.markdown(f"### 📋 {so_phieu}")
                with col_badge:
                    st.markdown(":red[DRAFT]")
                
                # Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                with col2:
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                
                # Rejection reason (if exists)
                if ly_do and str(ly_do).strip():
                    st.error(f"❌ **Lý do từ chối:** {ly_do}")
                    
                    # Parse who rejected (if format is "Name (Role): Reason")
                    if '(' in str(ly_do) and ')' in str(ly_do):
                        try:
                            rejector_info = str(ly_do).split(':')[0]
                            if 'qc_manager' in rejector_info.lower() or 'qc manager' in rejector_info.lower():
                                st.warning("⚠️ **Lưu ý:** Phiếu bị từ chối bởi QC Manager - Cần kiểm tra kỹ hướng giải quyết!")
                        except:
                            pass
                
                # Error details
                with st.expander("🔍 Chi tiết lỗi"):
                    ticket_rows = df_draft[df_draft['so_phieu'] == so_phieu]
                    if not ticket_rows.empty:
                        display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'muc_do']
                        available_cols = [col for col in display_cols if col in ticket_rows.columns]
                        st.dataframe(
                            ticket_rows[available_cols],
                            use_container_width=True,
                            hide_index=True
                        )
                
                # Action button
                st.write("")
                if st.button(
                    "🔄 GỬI LẠI ĐỂ PHÊ DUYỆT",
                    key=f"resubmit_{so_phieu}",
                    type="primary",
                    use_container_width=True
                ):
                    with st.spinner("Đang xử lý..."):
                        success, message = resubmit_ncr(so_phieu)
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

# --- TAB 2: PENDING APPROVAL ---
with tab2:
    st.subheader("⏳ Phiếu đang chờ duyệt")
    
    pending_statuses = ['cho_truong_ca', 'cho_truong_bp', 'cho_qc_manager', 'cho_giam_doc']
    df_pending = df_my_ncrs[df_my_ncrs['trang_thai'].isin(pending_statuses)]
    
    if df_pending.empty:
        st.info("ℹ️ Không có phiếu nào đang chờ duyệt")
    else:
        # Group by ticket
        tickets_pending = df_pending.groupby(['so_phieu', 'trang_thai']).agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'thoi_gian_cap_nhat': 'first'
        }).reset_index()
        
        for _, ticket in tickets_pending.iterrows():
            so_phieu = ticket['so_phieu']
            status = ticket['trang_thai']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            last_update = ticket.get('thoi_gian_cap_nhat', '')
            
            with st.container(border=True):
                # Header
                col_title, col_badge = st.columns([3, 1])
                with col_title:
                    st.markdown(f"### 📋 {so_phieu}")
                with col_badge:
                    status_color = get_status_color(status)
                    st.markdown(f":{status_color}[{get_status_display_name(status)}]")
                
                # Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                with col2:
                    if last_update:
                        st.write(f"🕐 **Cập nhật:** {last_update}")
                
                # Error details
                with st.expander("🔍 Chi tiết lỗi"):
                    ticket_rows = df_pending[df_pending['so_phieu'] == so_phieu]
                    if not ticket_rows.empty:
                        display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'muc_do']
                        available_cols = [col for col in display_cols if col in ticket_rows.columns]
                        st.dataframe(
                            ticket_rows[available_cols],
                            use_container_width=True,
                            hide_index=True
                        )

# --- TAB 3: COMPLETED ---
with tab3:
    st.subheader("✅ Phiếu đã hoàn thành")
    
    df_completed = df_my_ncrs[df_my_ncrs['trang_thai'] == 'hoan_thanh']
    
    if df_completed.empty:
        st.info("ℹ️ Chưa có phiếu nào hoàn thành")
    else:
        # Group by ticket
        tickets_completed = df_completed.groupby('so_phieu').agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'thoi_gian_cap_nhat': 'first'
        }).reset_index()
        
        st.success(f"🎉 Đã hoàn thành {len(tickets_completed)} phiếu!")
        
        for _, ticket in tickets_completed.iterrows():
            so_phieu = ticket['so_phieu']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            
            with st.expander(f"📋 {so_phieu} - {int(tong_loi)} lỗi"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                with col2:
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                
                # Error details
                ticket_rows = df_completed[df_completed['so_phieu'] == so_phieu]
                if not ticket_rows.empty:
                    display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'muc_do']
                    available_cols = [col for col in display_cols if col in ticket_rows.columns]
                    st.dataframe(
                        ticket_rows[available_cols],
                        use_container_width=True,
                        hide_index=True
                    )

# --- FOOTER ---
st.divider()
if st.button("🔙 Quay lại Dashboard"):
    st.switch_page("Dashboard.py")
