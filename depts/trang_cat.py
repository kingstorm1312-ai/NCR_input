from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận Tráng - Cắt
# Trích xuất từ pages/04_trang_cat.py
PROFILE = DeptProfile(
    code="trang_cat",
    name="Tráng Cắt",
    icon="✂️",
    prefix="TRANG_CAT_DYNAMIC", # Sẽ được xử lý đặc biệt trong engine
    config_group="trang_cat",
    has_measurements=False,
    has_checklist=False,
    skip_bp=True,
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA",
    has_aql=False,
    phan_loai_options=["Tráng", "Cắt"]
)
