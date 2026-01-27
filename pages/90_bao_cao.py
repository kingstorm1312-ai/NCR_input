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
    init_gspread,
    get_status_display_name,
    get_status_color
)
from core.services.report_service import (
    get_report_data,
    prepare_trend_data,
    prepare_pareto_data,
    prepare_dept_breakdown,
    prepare_severity_breakdown
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Báo Cáo Tổng Hợp", page_icon="📊", layout="wide")

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

# Inject Sidebar
from utils.ui_nav import render_sidebar
render_sidebar(st.session_state.user_info)

# --- ROLE CHECK ---
user_role = st.session_state.user_info.get("role", "")
ALLOWED_ROLES = ['director', 'admin', 'qc_manager', 'bgd_tan_phu']

if user_role not in ALLOWED_ROLES:
    st.error(f"⛔ Bạn không có quyền truy cập báo cáo này! (Role: {user_role})")
    if st.button("🔙 Quay lại trang chủ"):
        st.switch_page("Dashboard.py")
    st.stop()

# --- HEADER ---
st.title("📊 Báo Cáo & Phân Tích NCR")
st.markdown("---")

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu báo cáo..."):
    df_raw = get_report_data()

if df_raw.empty:
    st.info("Chưa có dữ liệu để báo cáo.")
    st.stop()

# --- FILTERS (SIDEBAR) ---
st.sidebar.header("🔍 Bộ lọc")

# 1. Filter Year
unique_years = sorted(df_raw['year'].dropna().unique().astype(int))
selected_years = st.sidebar.multiselect("Năm", unique_years) # Default empty = All

# Apply Year Filter
df_filtered = df_raw.copy()
if selected_years:
    df_filtered = df_filtered[df_filtered['year'].isin(selected_years)]

# 2. Filter Month
avail_months = sorted(df_filtered['month'].dropna().unique().astype(int))
selected_months = st.sidebar.multiselect("Tháng", avail_months)
if selected_months:
    df_filtered = df_filtered[df_filtered['month'].isin(selected_months)]

# 3. Filter Week
avail_weeks = sorted(df_filtered['week'].dropna().unique().astype(int))
selected_weeks = st.sidebar.multiselect("Tuần", avail_weeks)
if selected_weeks:
    df_filtered = df_filtered[df_filtered['week'].isin(selected_weeks)]

if df_filtered.empty:
    st.warning("Không có dữ liệu cho khoảng thời gian đã chọn.")
    st.stop()

# 4. Filter Department (Hierarchy)
# 4. Filter Department (Hierarchy)
if 'bo_phan_full' not in df_filtered.columns:
    df_filtered['bo_phan_full'] = df_filtered['bo_phan'].astype(str)

# Helper: Extract unique single departments from possibly comma-separated strings
all_depts_list = []
for bp in df_filtered['bo_phan'].dropna().unique():
    parts = [p.strip() for p in str(bp).replace('\n', ',').split(',') if p.strip()]
    all_depts_list.extend(parts)
unique_depts = sorted(list(set(all_depts_list)))

selected_depts = st.sidebar.multiselect("Bộ phận (Chính)", unique_depts)

# Apply Dept Filter (Contains Logic)
if selected_depts:
    # Filter: Keep row if ANY of its 'bo_phan' parts match selected_depts
    def match_dept(val):
        val_parts = [p.strip().lower() for p in str(val).replace('\n', ',').split(',')]
        sel_parts = [s.lower() for s in selected_depts]
        return any(v in sel_parts for v in val_parts)
        
    df_filtered = df_filtered[df_filtered['bo_phan'].apply(match_dept)]

# Filter Sub-Dept (Khâu) based on Dept - Logic similar if 'khau' is used separately, 
# but currently bo_phan_full is mostly same as bo_phan. 
# We'll skip secondary sub-dept strict filter to avoid complexity or apply same logic.
unique_sub_depts = sorted(df_filtered['bo_phan_full'].astype(str).unique())
# Optional: if user wants to filter unique raw strings from DB
# selected_sub_depts = st.sidebar.multiselect("Khâu (Raw Data)", unique_sub_depts)

df_final = df_filtered

# 5. Filter Contract with Grouping
# Extract Suffix (Last 3 chars)
def get_suffix(code):
    s = str(code).strip()
    return s[-3:] if len(s) >= 3 else "Khác"

df_final['contract_suffix'] = df_final['hop_dong'].apply(get_suffix)
unique_suffixes = sorted(df_final['contract_suffix'].unique())

selected_suffixes = st.sidebar.multiselect("Nhóm Hợp đồng (Đuôi 3 số)", unique_suffixes, 
                                          help="Chọn 3 số cuối của hợp đồng để lọc nhanh nhóm")

# Apply Suffix Filter First
if selected_suffixes:
    df_final = df_final[df_final['contract_suffix'].isin(selected_suffixes)]

# Then Filter Specific Contract
unique_contracts = sorted(df_final['hop_dong'].dropna().unique())
selected_contracts = st.sidebar.multiselect("Hợp đồng (Cụ thể)", unique_contracts)

if selected_contracts:
    df_final = df_final[df_final['hop_dong'].isin(selected_contracts)]

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
    # Chart 1: Trend over Time
    count_by_date = prepare_trend_data(df_final)
    fig_trend = px.line(count_by_date, x='date_obj', y='Total Errors', markers=True, 
                        title="Số lượng lỗi theo ngày", 
                        labels={'date_obj': 'Ngày', 'Total Errors': 'Số lượng lỗi'})
    fig_trend.update_traces(hovertemplate='Ngày: %{x}<br>Số lỗi: %{y}')
    st.plotly_chart(fig_trend, use_container_width=True)

# Chart 2: Pareto (Defect Types)
with col2:
    st.subheader("⚠️ Top Lỗi (Pareto)")
    count_by_error = prepare_pareto_data(df_final, top_n=10)
    
    # Pareto Chart
    fig_pareto = go.Figure()
    # Bar for Count
    fig_pareto.add_trace(go.Bar(
        x=count_by_error['ten_loi'].head(10), 
        y=count_by_error['count'].head(10),
        name='Số lượng',
        marker_color='indianred',
        hovertemplate='Lỗi: %{x}<br>Số lượng: %{y}<extra></extra>'
    ))
    # Line for Cum %
    fig_pareto.add_trace(go.Scatter(
        x=count_by_error['ten_loi'].head(10),
        y=count_by_error['cumulative_percent'].head(10),
        name='Tỷ lệ tích lũy %',
        yaxis='y2',
        mode='lines+markers',
        marker_color='blue',
        hovertemplate='Lỗi: %{x}<br>Tỷ lệ: %{y:.1f}%<extra></extra>'
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
    
    # Explode 'bo_phan' to count errors for EACH involved department
    count_by_dept = prepare_dept_breakdown(df_final)
    
    # Prettify Dept Name
    count_by_dept['Tên Khâu'] = count_by_dept['bo_phan_full']
    
    fig_dept = px.bar(count_by_dept, x='Tên Khâu', y='count', 
                      title="Tổng lỗi theo Khâu", color='count',
                      labels={'count': 'Số lượng lỗi'},
                      text='count')
    fig_dept.update_traces(hovertemplate='Khâu: %{x}<br>Số lỗi: %{y}<extra></extra>')
    st.plotly_chart(fig_dept, use_container_width=True)

# Chart 4: Severity Breakdown
with col4:
    st.subheader("🔥 Tỷ lệ Mức độ lỗi")
    if 'muc_do' in df_final.columns:
        count_by_sev = prepare_severity_breakdown(df_final)
        
        fig_sev = px.pie(count_by_sev, values='count', names='muc_do', 
                         title="Tỷ lệ Mức độ", hole=0.4,
                         color_discrete_map={'Nhẹ': 'mediumseagreen', 'Nặng': 'orange', 'Nghiêm trọng': 'red'})
        st.plotly_chart(fig_sev, use_container_width=True)
    else:
        st.info("Không có dữ liệu mức độ.")

# --- DOC GENERATOR ---
from docxtpl import DocxTemplate
from io import BytesIO
from utils.aql_manager import get_aql_standard # Import AQL Logic

def generate_docx(template_path, data_row):
    doc = DocxTemplate(template_path)
    
    # Calculate AQL Limits on-the-fly
    try:
        # NOTE: load_ncr_dataframe_v2 converts Sheet Headers to Internal Keys
        # Sheet: 'so_luong_lo_hang' -> Internal: 'sl_lo_hang'
        sl_lo_raw = data_row.get('sl_lo_hang', 0)
        # Fallback if raw data usage
        if not sl_lo_raw: sl_lo_raw = data_row.get('so_luong_lo_hang', 0)
        
        sl_lo = int(float(str(sl_lo_raw or 0)))
        aql_info = get_aql_standard(sl_lo)
        
        if aql_info:
            data_row['ac_major'] = aql_info['ac_major']
            data_row['ac_minor'] = aql_info['ac_minor']
            data_row['sample_size'] = aql_info['sample_size']
            data_row['aql_code'] = aql_info['code']
        else:
            data_row['ac_major'] = ""
            data_row['ac_minor'] = ""
            data_row['sample_size'] = ""
            data_row['aql_code'] = ""
    except:
        data_row['ac_major'] = ""
        data_row['ac_minor'] = ""

    # Ensure context has new fields empty string if missing
    for f in ['so_po', 'khach_hang', 'don_vi_kiem']:
        if f not in data_row:
            data_row[f] = ""

    doc.render(data_row)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

if st.button("📥 Xuất Báo Cáo (Word)"):
    # Demo: Export first selected row or just show functionality
    # In real app, might want to export specific NCR
    st.info("Chức năng xuất báo cáo mẫu đang được cập nhật để hỗ trợ in hàng loạt.")
    
    # Example logic for single export if user selects a ticket
    # ...
    pass

# --- DATA TABLE ---
with st.expander("📄 Xem dữ liệu chi tiết", expanded=True):
    # Rename columns for display
    display_cols_map = {
        'so_phieu': 'Số phiếu',
        'ngay_lap': 'Ngày lập',
        'ten_loi': 'Tên lỗi',
        'sl_loi': 'SL Lỗi',
        'trang_thai': 'Trạng thái',
        'bo_phan': 'Bộ phận',
        'nguoi_lap_phieu': 'Người lập',
        'hop_dong': 'Hợp đồng',
        # New cols
        'so_po': 'Số PO',
        'khach_hang': 'Khách hàng',
        'don_vi_kiem': 'ĐV Kiểm',
        'ma_vat_tu': 'Mã VT',
        'ten_sp': 'Tên SP',
        'phan_loai': 'Phân loại',
        'nguon_goc': 'Nguồn gốc',
        'vi_tri_loi': 'Vị trí',
        'don_vi_tinh': 'ĐVT',
        'muc_do': 'Mức độ',
        'thoi_gian_cap_nhat': 'Cập nhật lần cuối'
    }
    
    # Ensure new cols exist
    for c in ['so_po', 'khach_hang', 'don_vi_kiem']:
        if c not in df_final.columns:
            df_final[c] = ""

    df_display = df_final.rename(columns=display_cols_map)
    st.dataframe(df_display, use_container_width=True)
