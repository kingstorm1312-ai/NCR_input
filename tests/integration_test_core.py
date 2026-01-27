import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

# Mock st.secrets (If running standalone without streamlit run, secrets might fail unless we load them manually or run via streamlit)
# We will assume this is run via `streamlit run` OR we mock secrets if we want pure python.
# Easier to run via `python` if we manually patch secrets for testing.
# But `st.secrets` reads .streamlit/secrets.toml. Streamlit lib does this automatically even in script mode usually if config exists? 
# Actually no, `st.secrets` requires `streamlit run`. 
# Let's try to mock it by reading the toml manually if st.secrets fails, 
# OR just rely on the user having `secrets.toml` at valid path and we run it via `streamlit run tests/integration_test_core.py`.
# But `run_command` output handling for `streamlit run` is tricky (it blocks).
# Better to use a "headless" run or just python script that loads toml.

try:
    import toml
    with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
        secrets = toml.load(f)
    # Monkey patch st.secrets
    st.secrets = secrets
except Exception as e:
    print("Warning: Could not manually load secrets.toml. relying on environment or st defaults. " + str(e))

# Setup path
sys.path.append(os.getcwd())

from core.master_data import load_config_sheet
from core.gsheets import get_client, smart_append_batch, open_worksheet

def test_master_data():
    print("--- [TEST] CONFIG / MASTER DATA ---")
    try:
        # Note: load_config_sheet is cached, might need initial call setup
        # If not running in Streamlit, @st.cache won't work normally or might warn.
        # We can bypass cache or just call the logic.
        # But actually, compiling core modules imported streamlit.
        # Let's try calling it.
        list_noi, list_loi, list_vi, dict_muc, df_conf = load_config_sheet()
        print(f"✅ Loaded Config Success:")
        print(f"   - Nơi máy count: {len(list_noi)}")
        print(f"   - Lỗi count: {len(list_loi)}")
        print(f"   - Vị trí count: {len(list_vi)}")
        print(f"   - Mức độ rules: {len(dict_muc)}")
        
        if len(list_loi) > 0:
            print("   - Sample Defect: " + str(list_loi[0]))
        else:
            print("   ⚠️ Warning: Defect list empty.")
            
    except Exception as e:
        print(f"❌ FAIL: Master Data load failed: {e}")

def test_gsheet_append():
    print("\n--- [TEST] GSHEET CONNECT & APPEND ---")
    try:
        gc = get_client()
        if not gc:
            print("❌ FAIL: Could not get GSheet Client")
            return

        print("✅ GSheet Client Connected.")
        
        # Open Sheet
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ws = open_worksheet(spreadsheet_id, "NCR_DATA")
        if not ws:
            print("❌ FAIL: Could not open NCR_DATA worksheet")
            return
            
        print("✅ Opened Worksheet 'NCR_DATA'.")
        
        # Prepare Test Data
        test_row = {
            "ngay_lap": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "so_phieu_ncr": "TEST-PHASE1-VERIFY",
            "ten_loi": "TEST ROW - PLEASE DELETE",
            "mo_ta_loi": "Integration Test Row from Antigravity Agent",
            "nguoi_lap_phieu": "Antigravity Agent"
        }
        
        # Test Batch Append (List of dicts)
        success_count = smart_append_batch(ws, [test_row])
        
        if success_count == 1:
            print("✅ PASS: Successfully appended 1 test row.")
        else:
            print("❌ FAIL: smart_append_batch returned 0 success.")
            
    except Exception as e:
        print(f"❌ FAIL: GSheet Append Test Error: {e}")

if __name__ == "__main__":
    test_master_data()
    test_gsheet_append()
