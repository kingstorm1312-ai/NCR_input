import streamlit as st
import gspread
import json
import pandas as pd
from datetime import datetime, timedelta

@st.cache_resource
def get_client():
    """Initialize gspread client from secrets (Cached)."""
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        if isinstance(creds_str, str):
            creds_dict = json.loads(creds_str, strict=False)
        else:
            creds_dict = creds_str
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi khởi tạo gspread: {e}")
        return None

def open_worksheet(spreadsheet_id, worksheet_name):
    """Open a specific worksheet."""
    gc = get_client()
    if not gc: return None
    try:
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(worksheet_name)
        return ws
    except Exception as e:
        st.error(f"Lỗi mở Sheet '{worksheet_name}': {e}")
        return None

def smart_append_batch(worksheet, rows_data):
    """
    Append multiple rows to sheet, aligning with header.
    rows_data: List of dictionaries.
    """
    if not rows_data: return 0
    
    try:
        # 1. Get header row
        header_row = worksheet.row_values(1)
        if not header_row:
            st.error("Sheet chưa có Header!")
            return 0
            
        # 2. Prepare matched rows
        rows_to_append = []
        for row_dict in rows_data:
            ordered_row = []
            for col_name in header_row:
                val = row_dict.get(col_name, "")
                # Convert basic types to string if needed, or keep as is for gspread to handle (numbers)
                ordered_row.append(val)
            rows_to_append.append(ordered_row)
            
        # 3. Batch Append
        worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        return len(rows_to_append)
        
    except Exception as e:
        st.error(f"Lỗi lưu dữ liệu (Batch): {e}")
        return 0
