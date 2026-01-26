from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận May I
# Trích xuất từ pages/05_may_i.py và utils/config.py
PROFILE = DeptProfile(
    code="may_i",
    name="May I",
    icon="🧵",
    prefix="I'", # NCR_DEPARTMENT_PREFIXES["MAY_I"] trong utils/config.py (I' - Dòng 10)
    config_group="may", # Nhóm config dùng cho các bộ phận May
    has_measurements=True, # Dòng 187: tab_measure, tab_defects = st.tabs(["📏 Đo đạc & Checklist", ...])
    has_checklist=True,    # Dòng 187: st.tabs(["📏 Đo đạc & Checklist", ...])
    skip_bp=True,          # DEPARTMENTS_SKIP_BP trong utils/ncr_helpers.py (Dòng 54)
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"], # Dòng 384: open_worksheet(spreadsheet_id, ...)
    sheet_worksheet_name="NCR_DATA" # Dòng 384: open_worksheet(..., "NCR_DATA")
)
