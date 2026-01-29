
import sys
import os
import json
import streamlit as st

# Setup path
sys.path.append(os.getcwd())

# Mock st.secrets to avoid errors if not running via streamlit run
if not hasattr(st, "secrets"):
    try:
        import toml
        with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
            st.secrets = toml.load(f)
    except:
        print("Warning: Could not load secrets.toml")

from core.services.ai_tools import general_data_query


def test_query():
    output_lines = []
    output_lines.append("--- TESTING GENERAL DATA QUERY ---")
    
    # Test 1: Query with known Material Code
    output_lines.append("\n[TEST 1] Filter by 'ma_vat_tu' = 'Màng'")
    try:
        res1 = general_data_query({'ma_vat_tu': 'Màng'})
        output_lines.append(f"Result 1: {res1}")
    except Exception as e:
        output_lines.append(f"Result 1 ERROR: {e}")
    
    # Test 2: Query with multiple conditions
    output_lines.append("\n[TEST 2] Filter by 'ma_vat_tu'='Màng' AND 'muc_do'='Nặng'")
    try:
        res2 = general_data_query({'ma_vat_tu': 'Màng', 'muc_do': 'Nặng'})
        output_lines.append(f"Result 2: {res2}")
    except Exception as e:
        output_lines.append(f"Result 2 ERROR: {e}")
    
    # Test 3: Invalid column
    output_lines.append("\n[TEST 3] Filter by invalid column 'xyz_col'")
    try:
        res3 = general_data_query({'xyz_col': '123'})
        output_lines.append(f"Result 3: {res3}")
    except Exception as e:
        output_lines.append(f"Result 3 ERROR: {e}")

    # Write to file
    with open("tests/test_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print("Test finished. Results written to tests/test_output.txt")

if __name__ == "__main__":
    test_query()
