from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận Cắt Bàn
# Trích xuất từ pages/11_cat_ban.py
PROFILE = DeptProfile(
    code="cat_ban",
    name="Cắt Bàn",
    icon="🔪",
    prefix="CAT-BAN", # NCR_DEPARTMENT_PREFIXES["CAT_BAN"]
    config_group="cat_ban",
    has_measurements=False,
    has_checklist=False,
    skip_bp=True,
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA",
    has_aql=False
)
