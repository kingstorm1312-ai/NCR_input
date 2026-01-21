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
    calculate_stuck_time,
    get_status_display_name,
    get_status_color
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Dashboard Giám Đốc", page_icon="👑", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_role = user_info.get("role")

# --- ROLE CHECK (Director or Admin only) ---
if user_role not in ['director', 'admin']:
    st.error(f"⛔ Dashboard này chỉ dành cho Giám đốc! (Role của bạn: {user_role})")
    if st.button("🔙 Quay lại trang chủ"):
        st.switch_page("Dashboard.py")
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

# --- LOAD ALL NCR DATA ---
@st.cache_data(ttl=300)
def load_all_ncr_data():
    """Load tất cả NCR data từ Google Sheets"""
    try:
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        
        records = ws.get_all_records()
        df = pd.DataFrame(records)
        
        if df.empty:
            return pd.DataFrame()
        
        # Normalize column names
        df.columns = df.columns.str.strip()
        
        # Calculate stuck time
        if 'thoi_gian_cap_nhat' in df.columns:
            df['hours_stuck'] = df['thoi_gian_cap_nhat'].apply(calculate_stuck_time)
        else:
            df['hours_stuck'] = 0
        
        # Extract department from so_phieu
        if 'so_phieu' in df.columns:
            df['bo_phan'] = df['so_phieu'].astype(str).str.split('-').str[0].str.lower()
        
        return df
        
    except Exception as e:
        st.error(f"Lỗi load data: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()

# --- HEADER ---
st.title("👑 Dashboard Giám Đốc")
st.caption(f"Hệ thống giám sát luồng phê duyệt NCR")
st.divider()

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    df_all = load_all_ncr_data()

if df_all.empty:
    st.info("Chưa có dữ liệu NCR.")
    st.stop()

# --- PIPELINE STATUS ---
st.subheader("📊 Pipeline Status")

# Count by status
status_counts = df_all['trang_thai'].value_counts() if 'trang_thai' in df_all.columns else pd.Series()

# Define status order
status_order = ['draft', 'cho_truong_ca', 'cho_truong_bp', 'cho_qc_manager', 'cho_giam_doc', 'hoan_thanh']

# Create metrics
cols = st.columns(len(status_order))
for idx, status in enumerate(status_order):
    with cols[idx]:
        count = status_counts.get(status, 0)
        status_label = get_status_display_name(status)
        status_color = get_status_color(status)
        
        st.metric(
            label=status_label,
            value=count,
        )
        
        # Color indicator
        st.markdown(f":{status_color}[●]")

st.divider()

# --- BOTTLENECK ALERT ---
st.subheader("⚠️ Bottleneck Monitor (>24 giờ)")

# Filter stuck items (not completed and >24h)
df_stuck = df_all[
    (df_all['trang_thai'] != 'hoan_thanh') & 
    (df_all['hours_stuck'] > 24)
].copy()

# Group by ticket to avoid duplicates
if not df_stuck.empty and 'so_phieu' in df_stuck.columns:
    df_stuck_grouped = df_stuck.groupby('so_phieu', as_index=False).agg({
        'ngay_lap': 'first',
        'nguoi_lap_phieu': 'first',
        'trang_thai': 'first',
        'thoi_gian_cap_nhat': 'first',
        'hours_stuck': 'first',
        'bo_phan': 'first',
        'sl_loi': 'sum'
    }).sort_values('hours_stuck', ascending=False)
    
    if not df_stuck_grouped.empty:
        st.error(f"🚨 Phát hiện {len(df_stuck_grouped)} phiếu bị kẹt >24 giờ!")
        
        # Display stuck tickets
        for idx, row in df_stuck_grouped.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**📋 {row['so_phieu']}**")
                    st.caption(f"Bộ phận: {row.get('bo_phan', 'N/A').upper()}")
                
                with col2:
                    status_display = get_status_display_name(row['trang_thai'])
                    st.write(f"Trạng thái: **{status_display}**")
                    st.caption(f"Người lập: {row['nguoi_lap_phieu']}")
                
                with col3:
                    st.metric("Kẹt (giờ)", f"{row['hours_stuck']:.1f}")
    else:
        st.success("✅ Không có phiếu nào bị kẹt quá 24 giờ!")
else:
    st.success("✅ Không có phiếu nào bị kẹt quá 24 giờ!")

st.divider()

# --- STATISTICS OVERVIEW ---
st.subheader("📈 Thống kê tổng quan")

col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

with col_stat1:
    total_tickets = df_all['so_phieu'].nunique() if 'so_phieu' in df_all.columns else 0
    st.metric("Tổng số phiếu", total_tickets)

with col_stat2:
    total_errors = df_all['sl_loi'].sum() if 'sl_loi' in df_all.columns else 0
    st.metric("Tổng số lỗi", int(total_errors))

with col_stat3:
    completed = status_counts.get('hoan_thanh', 0)
    st.metric("Đã hoàn thành", completed, delta=None)

with col_stat4:
    pending = total_tickets - completed if 'so_phieu' in df_all.columns else 0
    st.metric("Đang xử lý", pending, delta_color="inverse")

st.divider()

# --- DEPARTMENT BREAKDOWN ---
st.subheader("🏢 Phân bổ theo bộ phận")

if 'bo_phan' in df_all.columns:
    # Group by department and status
    df_dept_status = df_all.groupby(['bo_phan', 'trang_thai']).size().reset_index(name='count')
    
    # Pivot for better display
    df_pivot = df_dept_status.pivot(index='bo_phan', columns='trang_thai', values='count').fillna(0)
    
    # Ensure all status columns exist
    for status in status_order:
        if status not in df_pivot.columns:
            df_pivot[status] = 0
    
    # Reorder columns
    df_pivot = df_pivot[[col for col in status_order if col in df_pivot.columns]]
    
    # Display
    st.dataframe(
        df_pivot.astype(int),
        use_container_width=True
    )
else:
    st.info("Không có dữ liệu bộ phận")

st.divider()

# --- TIME SERIES CHART ---
st.subheader("📅 Xu hướng theo thời gian")

if 'ngay_lap' in df_all.columns:
    # Try to parse date
    try:
        # Convert to datetime
        df_all['date_parsed'] = pd.to_datetime(df_all['ngay_lap'], errors='coerce')
        
        # Group by date
        df_time = df_all.groupby(df_all['date_parsed'].dt.date).size().reset_index(name='count')
        df_time.columns = ['Ngày', 'Số phiếu']
        
        # Plot
        st.line_chart(df_time.set_index('Ngày'))
    except:
        st.info("Không thể hiển thị chart theo thời gian")

# --- FOOTER ---
st.divider()

col_refresh, col_back = st.columns(2)
with col_refresh:
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_back:
    if st.button("🔙 Quay lại Dashboard", use_container_width=True):
        st.switch_page("Dashboard.py")
