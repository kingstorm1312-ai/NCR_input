import streamlit as st
import pandas as pd
import gspread
import json
import json
import sys
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import (
    load_ncr_dataframe,
    get_status_display_name,
    get_status_color
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Báo Cáo Tổng Hợp", page_icon="📊", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def init_gspread():
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
if not gc:
    st.stop()

# --- HEADER ---
st.title("📊 Báo Cáo & Phân Tích NCR")
st.markdown("---")

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu báo cáo..."):
    df_raw = load_ncr_dataframe(gc)

if df_raw.empty:
    st.info("Chưa có dữ liệu để báo cáo.")
    st.stop()

# --- FILTERS (SIDEBAR) ---
st.sidebar.header("🔍 Bộ lọc")

# 1. Filter Year
unique_years = sorted(df_raw['year'].dropna().unique().astype(int))
# Default to current year or all if current not exists
current_year = datetime.now().year
default_year = [current_year] if current_year in unique_years else unique_years
selected_years = st.sidebar.multiselect("Năm", unique_years, default=default_year)

# 2. Filter Month (Based on Year)
years_mask = df_raw['year'].isin(selected_years)
avail_months = sorted(df_raw[years_mask]['month'].dropna().unique().astype(int))
selected_months = st.sidebar.multiselect("Tháng", avail_months, default=avail_months)

# 3. Filter Week (Based on Month)
months_mask = years_mask & df_raw['month'].isin(selected_months)
avail_weeks = sorted(df_raw[months_mask]['week'].dropna().unique().astype(int))
selected_weeks = st.sidebar.multiselect("Tuần", avail_weeks, default=avail_weeks)

# Apply Time Filters
mask_time = (
    df_raw['year'].isin(selected_years) &
    df_raw['month'].isin(selected_months) &
    df_raw['week'].isin(selected_weeks)
)
df_filtered = df_raw[mask_time]

if df_filtered.empty:
    st.warning("Không có dữ liệu cho khoảng thời gian đã chọn.")
    st.stop()

# 4. Filter Department (Hierarchy)
# 'bo_phan' is top level (prefix), 'bo_phan_full' is sub-level (khâu)
if 'bo_phan_full' not in df_filtered.columns:
    df_filtered['bo_phan_full'] = df_filtered['bo_phan']

unique_depts = sorted(df_filtered['bo_phan'].dropna().unique())
selected_depts = st.sidebar.multiselect("Bộ phận (Chính)", unique_depts, default=unique_depts)

# Filter Sub-Dept (Khâu) based on Dept
dept_mask = df_filtered['bo_phan'].isin(selected_depts)
unique_sub_depts = sorted(df_filtered[dept_mask]['bo_phan_full'].dropna().unique())
selected_sub_depts = st.sidebar.multiselect("Khâu (Chi tiết)", unique_sub_depts, default=unique_sub_depts)

# Apply Dept Filters
mask_dept = df_filtered['bo_phan_full'].isin(selected_sub_depts)
df_final = df_filtered[mask_dept]

# 5. Filter Contract
unique_contracts = sorted(df_final['hop_dong'].dropna().unique())
selected_contracts = st.sidebar.multiselect("Hợp đồng", unique_contracts, default=unique_contracts)

# Apply Contract Filter
mask_contract = df_final['hop_dong'].isin(selected_contracts)
df_final = df_final[mask_contract]

if df_final.empty:
    st.warning("Không có dữ liệu phù hợp với bộ lọc.")
    st.stop()

st.success(f"Đang hiển thị: {len(df_final)} dòng lỗi từ {df_final['so_phieu'].nunique()} phiếu.")

# --- CHARTS ---

col1, col2 = st.columns(2)

# Chart 1: Trend over Time (By Week or Month)
with col1:
    st.subheader("📅 Xu hướng lỗi theo thời gian")
    # Group by Date (or Week)
    # Let's group by 'date_obj' (Daily) or 'week' depending on range duration
    # Simple line chart by Date
    count_by_date = df_final.groupby(df_final['date_obj'].dt.date).size().reset_index(name='Total Errors')
    fig_trend = px.line(count_by_date, x='date_obj', y='Total Errors', markers=True, 
                        title="Số lượng lỗi theo ngày", labels={'date_obj': 'Ngày', 'Total Errors': 'Số lỗi'})
    st.plotly_chart(fig_trend, use_container_width=True)

# Chart 2: Pareto (Defect Types)
with col2:
    st.subheader("⚠️ Top Lỗi (Pareto)")
    count_by_error = df_final['ten_loi'].value_counts().reset_index()
    count_by_error.columns = ['ten_loi', 'count']
    
    # Calculate Cumulative %
    count_by_error['cumulative_percent'] = (count_by_error['count'].cumsum() / count_by_error['count'].sum()) * 100
    
    # Pareto Chart
    fig_pareto = go.Figure()
    # Bar for Count
    fig_pareto.add_trace(go.Bar(
        x=count_by_error['ten_loi'].head(10), # Show top 10
        y=count_by_error['count'].head(10),
        name='Số lượng',
        marker_color='indianred'
    ))
    # Line for Cum %
    fig_pareto.add_trace(go.Scatter(
        x=count_by_error['ten_loi'].head(10),
        y=count_by_error['cumulative_percent'].head(10),
        name='Tỷ lệ tích lũy %',
        yaxis='y2',
        mode='lines+markers',
        marker_color='blue'
    ))
    
    fig_pareto.update_layout(
        title="Top 10 Loại Lỗi Thường Gặp",
        yaxis=dict(title='Số lượng'),
        yaxis2=dict(title='Tỷ lệ %', overlaying='y', side='right', range=[0, 100]),
        showlegend=False
    )
    st.plotly_chart(fig_pareto, use_container_width=True)


col3, col4 = st.columns(2)

# Chart 3: Department Performance
with col3:
    st.subheader("🏢 Phân bổ lỗi theo Bộ phận / Khâu")
    count_by_dept = df_final['bo_phan_full'].value_counts().reset_index()
    count_by_dept.columns = ['bo_phan_full', 'count']
    
    fig_dept = px.bar(count_by_dept, x='bo_phan_full', y='count', 
                      title="Tổng lỗi theo Khâu", color='count',
                      labels={'bo_phan_full': 'Khâu', 'count': 'Số lỗi'})
    st.plotly_chart(fig_dept, use_container_width=True)

# Chart 4: Severity Breakdown
with col4:
    st.subheader("🔥 Tỷ lệ Mức độ lỗi")
    if 'muc_do' in df_final.columns:
        count_by_sev = df_final['muc_do'].value_counts().reset_index()
        count_by_sev.columns = ['muc_do', 'count']
        
        fig_sev = px.pie(count_by_sev, values='count', names='muc_do', 
                         title="Tỷ lệ Mức độ", hole=0.4,
                         color_discrete_map={'Nhẹ': 'mediumseagreen', 'Nặng': 'orange', 'Nghiêm trọng': 'red'})
        st.plotly_chart(fig_sev, use_container_width=True)
    else:
        st.info("Không có dữ liệu mức độ.")

# --- DATA TABLE ---
with st.expander("📄 Xem dữ liệu chi tiết"):
    st.dataframe(df_final, use_container_width=True)
