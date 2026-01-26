from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận May P2
# Trích xuất từ pages/06_may_p2.py và utils/config.py
PROFILE = DeptProfile(
    code="may_p2",
    name="May P2",
    icon="🧵",
    prefix="P2", # NCR_DEPARTMENT_PREFIXES["MAY_P2"] trong utils/config.py (P2 - Dòng 11)
    config_group="may", # Nhóm config dùng cho các bộ phận May
    has_measurements=True, # Dòng 178: tab_measure, tab_defects = st.tabs(["📏 Đo đạc & Checklist", ...])
    has_checklist=True,    # Dòng 178: st.tabs(["📏 Đo đạc & Checklist", ...])
    skip_bp=True,          # DEPARTMENTS_SKIP_BP trong utils/ncr_helpers.py (Dòng 55)
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"], # Dòng 374: open_worksheet(spreadsheet_id, ...)
    sheet_worksheet_name="NCR_DATA" # Dòng 374: open_worksheet(..., "NCR_DATA")
)
