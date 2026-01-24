import streamlit as st
import pandas as pd
import gspread
import json

def init_gspread_standalone():
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

def debug_image():
    try:
        st.write("Fetching FI-01-34...")
        gc = init_gspread_standalone()
        if not gc: return

        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("NCR_DATA")
        
        # Get all records
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Filter
        target = "FI-01-34"
        if 'so_phieu_ncr' in df.columns:
            row = df[df['so_phieu_ncr'] == target]
            if not row.empty:
                raw_val = row.iloc[0]['hinh_anh']
                st.write(f"Raw 'hinh_anh' for {target}:")
                st.code(repr(raw_val)) # Use repr to see hidden characters like \r \n
                
                st.write("Splitting by \\n:")
                parts = str(raw_val).split('\n')
                st.write(parts)
            else:
                st.error(f"Ticket {target} not found")
        else:
            st.error("Column 'so_phieu_ncr' not found")

    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    debug_image()
