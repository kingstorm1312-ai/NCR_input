from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận FI (Finished Goods)
# Trích xuất từ pages/01_fi.py và utils/config.py
PROFILE = DeptProfile(
    code="fi",
    name="FI",
    icon="🔍",
    prefix="FI", # NCR_DEPARTMENT_PREFIXES["FI"] trong utils/config.py
    config_group="fi",
    has_measurements=True, # Dòng 192: tab_measure, tab_defects = st.tabs(["📏 Đo đạc & Checklist", "🐞 Chi tiết Lỗi"])
    has_checklist=True,    # Dòng 192: st.tabs(["📏 Đo đạc & Checklist", ...])
    skip_bp=True,          # DEPARTMENTS_SKIP_BP trong utils/ncr_helpers.py (Dòng 51)
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"], # Dòng 397: open_worksheet(spreadsheet_id, ...)
    sheet_worksheet_name="NCR_DATA" # Dòng 397: open_worksheet(..., "NCR_DATA")
)
