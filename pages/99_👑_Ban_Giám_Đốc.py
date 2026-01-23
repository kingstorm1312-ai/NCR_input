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
    init_gspread,
    calculate_stuck_time,
    get_status_display_name,
    get_status_color,
    COLUMN_MAPPING,
    load_ncr_dataframe_v2
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

# --- LOAD ALL NCR DATA ---
# Using shared loader from utils
def load_all_ncr_data():
    return load_ncr_dataframe_v2()

# --- HEADER ---
st.title("👑 Dashboard Giám Đốc")
st.caption(f"Hệ thống giám sát luồng phê duyệt NCR")
st.divider()

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    df_raw = load_all_ncr_data()

if df_raw.empty:
    st.info("Chưa có dữ liệu NCR.")
    st.stop()

# --- DATA PREPROCESSING: GROUP BY TICKET ---
# Raw data has 1 row per Error. We need 1 row per Ticket for stats.
if 'so_phieu' in df_raw.columns:
    group_cols = {
        'ngay_lap': 'first',
        'nguoi_lap_phieu': 'first',
        'trang_thai': 'first',
        'thoi_gian_cap_nhat': 'first',
        'hours_stuck': 'first',
        'sl_loi': 'sum',
        'bo_phan': 'first'
    }
    # Add optional cols if exist
    for col in df_raw.columns:
        if col not in group_cols and col != 'so_phieu':
            group_cols[col] = 'first'
            
    df_all = df_raw.groupby('so_phieu', as_index=False).agg(group_cols)
else:
    df_all = df_raw.copy()

# --- PIPELINE STATUS ---
st.subheader("📊 Pipeline Status")

# Count by status (Now counting Tickets, not Error Rows)
status_counts = df_all['trang_thai'].value_counts() if 'trang_thai' in df_all.columns else pd.Series()

# Define status order (Must cover ALL active statuses)
status_order = [
    'draft', 
    'cho_truong_ca', 
    'cho_truong_bp', 
    'cho_qc_manager', 
    'cho_giam_doc', 
    'cho_bgd_tan_phu', # NEW
    'hoan_thanh'
]

# Create metrics
# Check if there are any old rejection statuses
rejection_count = 0
for status, count in status_counts.items():
    if 'tu_choi' in str(status):
        rejection_count += count

# Columns: Standard Flow + Rejections (if any)
total_cols = len(status_order) + (1 if rejection_count > 0 else 0)
cols = st.columns(total_cols)

for idx, status in enumerate(status_order):
    with cols[idx]:
        count = status_counts.get(status, 0)
        status_label = get_status_display_name(status)
        status_color = get_status_color(status)
        
        # Abbreviate long labels for Dashboard
        if 'BGĐ Tân Phú' in status_label:
            status_label = 'BGĐ Tân Phú'
        
        st.metric(
            label=status_label,
            value=count,
        )
        st.markdown(f":{status_color}[●]")

# Display Rejections column if data exists
if rejection_count > 0:
    with cols[-1]:
        st.metric(label="Bị từ chối (Legacy)", value=rejection_count)
        st.markdown(":red[●]")

st.divider()

# --- BOTTLENECK ALERT ---
st.subheader("⚠️ Bottleneck Monitor (>24 giờ)")

# Filter stuck items (not completed and >24h)
df_stuck = df_all[
    (df_all['trang_thai'] != 'hoan_thanh') & 
    (df_all['hours_stuck'] > 24)
].copy()

# Group by ticket to avoid duplicates (Already grouped, but safe to keep logic simple)
if not df_stuck.empty and 'so_phieu' in df_stuck.columns:
    df_stuck_grouped = df_stuck # Already grouped
    
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

col_stat1, col_stat2, col_stat3 = st.columns(3)

with col_stat1:
    total_tickets = df_all['so_phieu'].nunique() if 'so_phieu' in df_all.columns else 0
    st.metric("Tổng số phiếu", total_tickets)

with col_stat2:
    completed = status_counts.get('hoan_thanh', 0)
    st.metric("Đã hoàn thành", completed, delta=None)

with col_stat3:
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
        # Use pre-parsed date_obj from shared loader
        # Group by date
        if 'date_obj' in df_all.columns:
            df_time = df_all.groupby(df_all['date_obj'].dt.date).size().reset_index(name='count')
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
