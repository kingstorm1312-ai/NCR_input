from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận May N4
# Trích xuất từ pages/07_may_n4.py
PROFILE = DeptProfile(
    code="may_n4",
    name="May N4",
    icon="🧵",
    prefix="MAY_N4", # NCR_DEPARTMENT_PREFIXES["MAY_N4"]
    config_group="may_n4",
    has_measurements=True,
    has_checklist=True,
    skip_bp=True, # Tương tự các bộ phận May khác
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA"
)
