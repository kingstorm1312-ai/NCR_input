
import streamlit as st
import pandas as pd
import sys
import os

# We are inside NCR_mobile_project, so we can import directly
sys.path.append(os.getcwd())
from core.services.report_service import get_report_data
from utils.ncr_helpers import COLUMN_MAPPING



try:
    output_lines = []

    output_lines.append("--- DEBUG DATA LOADING ---")
    st.write("Fetching request...")
    df = get_report_data()
    
    output_lines.append(f"Total DataFrame Rows: {len(df)}")
    output_lines.append(f"Columns: {list(df.columns)}")
    
    # Check mapping
    output_lines.append("Mapping check:")
    if 'ngay_lap' in df.columns:
        output_lines.append("✅ 'ngay_lap' column exists.")
    else:
        output_lines.append("❌ 'ngay_lap' MISSING.")
        mapped_ngay = COLUMN_MAPPING.get('ngay_lap')
        output_lines.append(f"COLUMN_MAPPING['ngay_lap'] -> {mapped_ngay}")
        
    if 'year' in df.columns:
        unique_years = df['year'].dropna().unique()
        output_lines.append(f"Unique Years: {unique_years}")
        
        c2025 = len(df[df['year'] == 2025])
        output_lines.append(f"Rows with year=2025: {c2025}")
    else:
        output_lines.append("❌ 'year' derived column missing.")
        
    if 'date_obj' in df.columns:
         null_dates = df['date_obj'].isna().sum()
         output_lines.append(f"Rows with Null Date: {null_dates} / {len(df)}")
    
    output_lines.append("--------------------------")
    
    with open("debug_data_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print("Logged to debug_data_log.txt")

except Exception as e:
    with open("debug_data_log.txt", "w", encoding="utf-8") as f:
        f.write(f"❌ Error: {e}")
