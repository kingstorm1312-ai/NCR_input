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

def get_top_defects(top_n=5, contract=None, department=None, year=None, month=None):
    """
    Returns top N most common defects, optionally filtered by criteria.
    Args:
        top_n (int): Number of top defects to return.
        contract (str): Filter by contract code.
        department (str): Filter by department.
        year (int): Filter by year.
        month (int): Filter by month.
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    # Apply Filters
    if contract:
        df = df[df['hop_dong'].astype(str).str.contains(contract, case=False, na=False)]
    
    if department:
        col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        df = df[df[col].astype(str).str.contains(department, case=False, na=False)]
        
    if year:
        df = df[df['year'] == int(year)]
        
    if month:
        df = df[df['month'] == int(month)]
        
    if df.empty: return "No data matching filters."
    
    # Sum quantities by defect type instead of counting rows
    if 'sl_loi' in df.columns:
        df['sl_loi_val'] = pd.to_numeric(df['sl_loi'], errors='coerce').fillna(0)
        counts = df.groupby('ten_loi')['sl_loi_val'].sum().sort_values(ascending=False).head(int(top_n)).astype(int).to_dict()
    else:
        # Fallback to count if sl_loi not available
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
    errors = ticket[['ten_loi', 'sl_loi', 'md_loi', 'vi_tri_loi']].to_dict('records')
    
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

def get_contract_ranking(top_n=5, department=None, year=None, month=None):
    """
    Xếp hạng các Hợp đồng (cụ thể) có nhiều lỗi nhất.
    Có thể lọc theo bộ phận hoặc thời gian.
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    # Apply Filters
    if department:
        col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        df = df[df[col].astype(str).str.contains(department, case=False, na=False)]
    if year: df = df[df['year'] == int(year)]
    if month: df = df[df['month'] == int(month)]
    
    # Count unique tickets per contract
    ranking = df.groupby('hop_dong')['so_phieu'].nunique().sort_values(ascending=False).head(int(top_n)).to_dict()
    return json.dumps(ranking, ensure_ascii=False)

def get_contract_group_ranking(top_n=5, department=None, year=None, month=None):
    """
    Xếp hạng NHÓM Hợp đồng (dưới 3 ký tự cuối hoặc tiền tố) có nhiều lỗi nhất.
    Có thể lọc theo bộ phận hoặc thời gian.
    Dùng cho: "Nhóm hợp đồng nào nhiều lỗi nhất?" hoặc "Nhóm hợp đồng nào lỗi nhiều nhất ở khâu FI?"
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    # Apply Filters
    if department:
        col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        df = df[df[col].astype(str).str.contains(department, case=False, na=False)]
    if year: df = df[df['year'] == int(year)]
    if month: df = df[df['month'] == int(month)]
    
    # Group Logic (Suffix)
    # Group Logic (Suffix)
    df['group'] = df['hop_dong'].apply(lambda x: str(x).strip()[-3:] if len(str(x).strip()) >= 3 else "Khác")
    # Count unique tickets per group
    ranking = df.groupby('group')['so_phieu'].nunique().sort_values(ascending=False).head(int(top_n)).to_dict()
    return json.dumps(ranking, ensure_ascii=False)

def general_data_query(filter_conditions: dict) -> str:
    """
    Lọc dữ liệu NCR theo bất kỳ cột nào.
    
    Args:
        filter_conditions (dict): Dictionary các điều kiện lọc.
            Keys: Tên cột (vd: 'ma_vat_tu', 'nguon_goc', 'vi_tri_loi')
            Values: Giá trị cần tìm (hỗ trợ partial match)
    
    Returns:
        str: JSON summary của kết quả lọc.
    
    Example:
        filter_conditions = {
            'ma_vat_tu': 'VT001',
            'nguon_goc': 'NCC ABC',
            'vi_tri_loi': 'Mép túi'
        }
    """
    with st.spinner("Đang truy vấn dữ liệu theo yêu cầu..."):
        df = get_report_data()
        if df.empty:
            return json.dumps({"status": "error", "message": "No data available"})
    
        applied_filters = {}
        
        # Make a copy to avoid SettingWithCopyWarning if any
        df = df.copy()
        
        for col, val in filter_conditions.items():
            # Validate input
            if not val: continue
            val_str = str(val).strip()
            if not val_str: continue

            if col in df.columns:
                # Dynamic Filter: Case-insensitive contains
                try:
                    df = df[df[col].astype(str).str.contains(val_str, case=False, na=False)]
                    applied_filters[col] = val_str
                except Exception as e:
                    # Fallback if regex fails (e.g. invalid regex chars)
                    # Try literal string match if contains fails, or ignore
                    try:
                        df = df[df[col].astype(str).str.lower() == val_str.lower()]
                        applied_filters[col] = val_str
                    except:
                        pass
        
        if df.empty:
            return json.dumps({
                "status": "success",
                "filters_applied": applied_filters,
                "total_errors": 0,
                "message": "Không tìm thấy dữ liệu khớp với điều kiện lọc."
            }, ensure_ascii=False)
        
        # Aggregate insights
        total_count = len(df)
        unique_tickets = df['so_phieu'].nunique() if 'so_phieu' in df.columns else 0
        
        # Calculate Defect Quantities and Error Rate
        total_defect_qty = 0
        total_inspected_qty = 0
        error_rate = 0.0
        
        # NOTE: Column names after mapping: sl_loi (so_luong_loi), sl_kiem (so_luong_kiem)
        if 'sl_loi' in df.columns:
            total_defect_qty = pd.to_numeric(df['sl_loi'], errors='coerce').fillna(0).sum()
            
        if 'sl_kiem' in df.columns:
            # FIX: Only sum sl_kiem for unique tickets, avoiding duplicates from multiple defect rows
            # Assuming same sl_kiem for all rows in same ticket
            df_unique_tickets = df.drop_duplicates('so_phieu')
            total_inspected_qty = pd.to_numeric(df_unique_tickets['sl_kiem'], errors='coerce').fillna(0).sum()
            
        if total_inspected_qty > 0:
            error_rate = (total_defect_qty / total_inspected_qty) * 100
        
        # Helper to calculate stats per group
        data_warnings = []
        
        if total_inspected_qty > 0 and total_defect_qty > total_inspected_qty:
             data_warnings.append(f"CẢNH BÁO: Tổng số lỗi ({total_defect_qty}) lớn hơn tổng kiểm ({total_inspected_qty}). Tỷ lệ lỗi > 100%. Vui lòng kiểm tra lại dữ liệu nguồn.")

        def get_group_stats(dataframe, group_col):
             if group_col not in dataframe.columns: return {}
             
             stats = {}
             # Group by unique values
             groups = dataframe[group_col].dropna().unique()
             
             for g in groups:
                 sub_df = dataframe[dataframe[group_col] == g]
                 
                 # Qty
                 qty = 0
                 if 'sl_loi' in sub_df.columns:
                     qty = pd.to_numeric(sub_df['sl_loi'], errors='coerce').fillna(0).sum()
                 
                 # Insp (dedup so_phieu)
                 insp = 0
                 if 'so_phieu' in sub_df.columns and 'sl_kiem' in sub_df.columns:
                     sub_df_unique = sub_df.drop_duplicates('so_phieu')
                     insp = pd.to_numeric(sub_df_unique['sl_kiem'], errors='coerce').fillna(0).sum()
                 
                 rate = (qty / insp * 100) if insp > 0 else 0.0
                 
                 # Check anomaly
                 if insp > 0 and qty > insp:
                      data_warnings.append(f"Cảnh báo: '{g}' có số lỗi ({qty}) > số kiểm ({insp}). Tỷ lệ: {rate:.2f}%")
                 
                 stats[str(g)] = {
                     "qty": int(qty),
                     "inspected": int(insp),
                     "rate_pct": round(rate, 2)
                 }
            
             # Sort by qty desc and take top 5
             sorted_stats = dict(sorted(stats.items(), key=lambda item: item[1]['qty'], reverse=True)[:5])
             return sorted_stats

        # Top Defects (Keep simple for now or update? User asked for formulas)
        # For Defects, Rate is usually vs Global Inspected, not "Inspected of Ticket containing defect"
        # Let's keep Top Defects simple (Qty) but add Rate vs Global
        top_defects = {}
        if 'ten_loi' in df.columns and 'sl_loi' in df.columns:
            # Ensure numeric val
            df_temp = df.copy()
            df_temp['sl_loi_val'] = pd.to_numeric(df_temp['sl_loi'], errors='coerce').fillna(0)
            
            # Group sum
            defect_sums = df_temp.groupby('ten_loi')['sl_loi_val'].sum().sort_values(ascending=False).head(5)
            
            for name, val in defect_sums.items():
                rate = (val / total_inspected_qty * 100) if total_inspected_qty > 0 else 0.0
                top_defects[name] = {
                    "qty": int(val),
                    "rate_global_pct": round(rate, 2)
                }

        # Top Sources (Detailed Rate)
        top_sources = get_group_stats(df, 'nguon_goc')

        # Top Departments
        target_col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        top_depts = get_group_stats(df, target_col)
        
        # Top Contracts (Keep ticket count)
        top_contracts = {}
        top_contract_groups = {}
        if 'hop_dong' in df.columns and 'so_phieu' in df.columns:
            # Count unique tickets
            unique_counts = df.groupby('hop_dong')['so_phieu'].nunique().sort_values(ascending=False).head(10)
            top_contracts = unique_counts.to_dict()
            
            # Calculate groups (Suffix last 3 chars)
            groups = df['hop_dong'].apply(lambda x: str(x).strip()[-3:] if len(str(x).strip()) >= 3 else "Khác")
            # Create temp df for grouping
            df_temp = df.copy()
            df_temp['group'] = groups
            top_contract_groups = df_temp.groupby('group')['so_phieu'].nunique().sort_values(ascending=False).head(5).to_dict()

        return json.dumps({
            "status": "success",
            "filters_applied": applied_filters,
            "data_warnings": data_warnings,
            "total_errors": total_count,
            "total_tickets": unique_tickets,
            "total_defect_qty": int(total_defect_qty),
            "total_inspected_qty": int(total_inspected_qty),
            "error_rate_percent": round(error_rate, 2),
            "top_5_defects": top_defects,
            "top_5_sources": top_sources,
            "top_3_departments": top_depts,
            "top_10_contracts": top_contracts,
            "top_5_contract_groups": top_contract_groups
        }, ensure_ascii=False)

def get_top_ticket_by_defects(top_n=5, department=None, year=None, month=None):
    """
    Tìm các PHIẾU NCR có tổng số lượng lỗi cao nhất.
    Dùng cho câu hỏi: "Phiếu nào nhiều lỗi nhất?", "Top phiếu lỗi cao nhất"
    """
    df = get_report_data()
    if df.empty: return "No data."
    
    # Filter logic
    if department:
        col = 'bo_phan_full' if 'bo_phan_full' in df.columns else 'bo_phan'
        df = df[df[col].astype(str).str.contains(department, case=False, na=False)]
    if year: df = df[df['year'] == int(year)]
    if month: df = df[df['month'] == int(month)]
    
    if df.empty: return "No data matching filters."
    
    # Group by Ticket (so_phieu) and Sum defect quantity (sl_loi)
    if 'so_phieu' in df.columns and 'sl_loi' in df.columns:
         df['sl_loi_val'] = pd.to_numeric(df['sl_loi'], errors='coerce').fillna(0)
         ranking = df.groupby('so_phieu')['sl_loi_val'].sum().sort_values(ascending=False).head(int(top_n)).to_dict()
         return json.dumps(ranking, ensure_ascii=False)
         
    return json.dumps({"error": "Missing columns"}, ensure_ascii=False)
