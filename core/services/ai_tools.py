import pandas as pd
import streamlit as st
from datetime import datetime
from core.services.report_service import get_report_data
import json

def filter_data(contract=None, department=None, year=None, month=None, defect_name=None):
    """
    Filters NCR data and returns a summary.
    
    Args:
        contract (str): Partial or full contract code.
        department (str): Department name.
        year (int): Year (e.g., 2024).
        month (int): Month (1-12).
        defect_name (str): Partial defect name.
    
    Returns:
        str: JSON string summary of filtered data (Total count, filtered criteria).
    """
    df = get_report_data()
    
    # 1. Apply Filters
    if contract:
        df = df[df['hop_dong'].astype(str).str.contains(contract, case=False, na=False)]
    
    if department:
        # Check bo_phan_full if exists, else bo_phan
        col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        df = df[df[col].astype(str).str.contains(department, case=False, na=False)]
        
    if year:
        df = df[df['year'] == int(year)]
        
    if month:
        df = df[df['month'] == int(month)]
        
    if defect_name:
        df = df[df['ten_loi'].astype(str).str.contains(defect_name, case=False, na=False)]
        
    # 2. Aggregations for Insight
    total_count = len(df)
    unique_tickets = df['so_phieu'].nunique() if not df.empty else 0
    
    top_defects = {}
    if not df.empty and 'ten_loi' in df.columns:
        top_defects = df['ten_loi'].value_counts().head(3).to_dict()
        
    top_depts = {}
    if not df.empty:
         col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
         top_depts = df[col].value_counts().head(3).to_dict()

    return json.dumps({
        "status": "success",
        "filter_applied": {
            "contract": contract, "department": department, 
            "year": year, "month": month, "defect_name": defect_name
        },
        "total_errors": total_count,
        "total_tickets": unique_tickets,
        "top_3_defects": top_defects,
        "top_3_departments": top_depts
    }, ensure_ascii=False)

def get_top_defects(top_n=5):
    """Returns top N most common defects from ALL data."""
    df = get_report_data()
    if df.empty: return "No data."
    
    counts = df['ten_loi'].value_counts().head(int(top_n)).to_dict()
    return json.dumps(counts, ensure_ascii=False)

def compare_periods(period1, period2):
    """
    Compares error counts between two periods (YYYY-MM).
    
    Args:
        period1 (str): "YYYY-MM"
        period2 (str): "YYYY-MM"
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    def get_count(p_str):
        try:
            y, m = map(int, p_str.split('-'))
            return len(df[(df['year'] == y) & (df['month'] == m)])
        except:
            return 0
            
    c1 = get_count(period1)
    c2 = get_count(period2)
    
    diff = c1 - c2
    percent_diff = (diff / c2 * 100) if c2 > 0 else 100 if c1 > 0 else 0
    
    return json.dumps({
        "period1": period1, "count1": c1,
        "period2": period2, "count2": c2,
        "difference": diff,
        "percent_change": round(percent_diff, 1)
    })

def get_department_ranking():
    """Returns departments ranked by total errors."""
    df = get_report_data()
    if df.empty: return "No data."
    
    col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
    ranking = df[col].value_counts().to_dict()
    return json.dumps(ranking, ensure_ascii=False)

def get_ncr_details(ncr_id):
    """
    Gets details of a specific NCR ticket.
    
    Args:
        ncr_id (str): Full NCR ID (e.g. NCR-FI-01-05).
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    # Filter exact match
    ticket = df[df['so_phieu'] == ncr_id]
    
    if ticket.empty:
        return f"Không tìm thấy phiếu có mã {ncr_id}"
        
    # Aggregate errors in this ticket
    errors = ticket[['ten_loi', 'sl_loi', 'muc_do', 'vi_tri_loi']].to_dict('records')
    
    # Get metadata from first row
    first_row = ticket.iloc[0]
    
    info = {
        "ncr_id": ncr_id,
        "date": str(first_row.get('ngay_lap', '')),
        "contract": first_row.get('hop_dong', ''),
        "department": first_row.get('bo_phan', ''),
        "creator": first_row.get('nguoi_lap_phieu', ''),
        "images": first_row.get('hinh_anh', ''),
        "errors": errors
    }
    
    return json.dumps(info, ensure_ascii=False)
