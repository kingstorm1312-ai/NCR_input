import pandas as pd
import streamlit as st
from utils.ncr_helpers import load_ncr_dataframe_v2
import streamlit as st

# FORCE CACHE UPDATE 2026-01-29
# FORCE CACHE UPDATE 2026-01-29
@st.cache_data(ttl=300)
def get_report_data():
    """
    Tải dữ liệu NCR và lọc bỏ các phiếu đã hủy.
    """
    df_raw = load_ncr_dataframe_v2()
    if not df_raw.empty and 'trang_thai' in df_raw.columns:
        # Loại bỏ các phiếu đã hủy khỏi báo cáo
        df_raw = df_raw[df_raw['trang_thai'] != 'da_huy'].copy()
    return df_raw

def prepare_trend_data(df):
    """
    Chuẩn bị dữ liệu xu hướng lỗi theo thời gian (ngày).
    """
    if df.empty:
        return pd.DataFrame(columns=['date_obj', 'Total Errors'])
        
    count_by_date = df.groupby(df['date_obj'].dt.date).size().reset_index(name='Total Errors')
    return count_by_date

def prepare_pareto_data(df, top_n=10):
    """
    Chuẩn bị dữ liệu cho biểu đồ Pareto (Top loại lỗi).
    """
    if df.empty or 'ten_loi' not in df.columns:
        return pd.DataFrame(columns=['ten_loi', 'count', 'cumulative_percent'])
        
    count_by_error = df['ten_loi'].value_counts().reset_index()
    count_by_error.columns = ['ten_loi', 'count']
    
    # Tính % tích lũy
    count_by_error['cumulative_percent'] = (count_by_error['count'].cumsum() / count_by_error['count'].sum()) * 100
    
    return count_by_error.head(top_n)

def prepare_dept_breakdown(df):
    """
    Chuẩn bị dữ liệu phân bổ lỗi theo bộ phận/khâu.
    """
    if df.empty or 'bo_phan_full' not in df.columns:
        return pd.DataFrame(columns=['bo_phan_full', 'count'])
        
    # Tách các bộ phận nếu có nhiều bộ phận ngăn cách bởi dấu phẩy
    df_exploded = df.assign(
        bo_phan_split=df['bo_phan_full'].astype(str).str.replace('\n', ',').str.split(',')
    ).explode('bo_phan_split')
    
    df_exploded['bo_phan_split'] = df_exploded['bo_phan_split'].str.strip()
    df_exploded = df_exploded[df_exploded['bo_phan_split'] != '']
    
    count_by_dept = df_exploded['bo_phan_split'].value_counts().reset_index()
    count_by_dept.columns = ['bo_phan_full', 'count']
    
    return count_by_dept

def prepare_severity_breakdown(df):
    """
    Chuẩn bị dữ liệu mức độ lỗi.
    """
    if df.empty or 'muc_do' not in df.columns:
        return pd.DataFrame(columns=['muc_do', 'count'])
        
    count_by_sev = df['muc_do'].value_counts().reset_index()
    count_by_sev.columns = ['muc_do', 'count']
    
    return count_by_sev
