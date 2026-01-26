from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận ĐV Cuộn
# Trích xuất từ pages/02_dv_cuon.py
PROFILE = DeptProfile(
    code="dv_cuon",
    name="ĐV Cuộn",
    icon="💿",
    prefix="DVCUON", # NCR_DEPARTMENT_PREFIXES["DV_CUON"]
    config_group="dv_cuon",
    has_measurements=False,
    has_checklist=False,
    skip_bp=True, # Dòng 52 trong utils/ncr_helpers.py
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA",
    has_aql=False,
    phan_loai_options=["", "Cuộn màng", "Cuộn PP", "Cuộn VKD", "Cuộn RPET", "Cuộn giấy", "Cuộn in", "Cuộn HDPE"]
)
