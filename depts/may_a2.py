from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận May A2
# Trích xuất từ pages/08_may_a2.py
PROFILE = DeptProfile(
    code="may_a2",
    name="May A2",
    icon="🧵",
    prefix="MAY_A2", # NCR_DEPARTMENT_PREFIXES["MAY_A2"]
    config_group="may_a2",
    has_measurements=True,
    has_checklist=True,
    skip_bp=True,
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA"
)
