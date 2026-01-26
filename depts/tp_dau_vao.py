from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận TP Đầu Vào
# Trích xuất từ pages/09_tp_dau_vao.py
PROFILE = DeptProfile(
    code="tp_dau_vao",
    name="TP Đầu Vào",
    icon="📦",
    prefix="TPDV", # NCR_DEPARTMENT_PREFIXES["TP_DAU_VAO"]
    config_group="tp_dau_vao",
    has_measurements=True,
    has_checklist=True,
    skip_bp=True, # Dòng 57 trong utils/ncr_helpers.py
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA"
)
