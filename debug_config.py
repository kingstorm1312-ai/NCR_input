import streamlit as st
import pandas as pd
import gspread
import json

def init_gspread_standalone():
    """Khởi tạo gspread client từ secrets (Standalone copy)"""
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
        print(f"Lỗi khởi tạo gspread: {e}")
        return None

def debug_config():
    try:
        st.write("Starting Debug...")
        gc = init_gspread_standalone()
        if not gc:
            st.error("Failed to init gspread")
            return

        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("CONFIG")
        df = pd.DataFrame(ws.get_all_records())
        
        st.write("COLUMNS:", df.columns.tolist())
        
        if 'nhom_loi' in df.columns:
            unique_vals = df['nhom_loi'].unique().tolist()
            st.write("UNIQUE nhom_loi:", unique_vals)
            print("UNIQUE nhom_loi:", unique_vals)
        else:
            st.error("Column 'nhom_loi' NOT FOUND")
            
        if 'ten_loi' in df.columns:
            head_vals = df['ten_loi'].head(10).tolist()
            st.write("First 10 ten_loi:", head_vals)
        else:
            st.error("Column 'ten_loi' NOT FOUND")

    except Exception as e:
        st.error(f"Error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_config()
