from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận Xưởng In
# Trích xuất từ pages/10_in_xuong_d.py
PROFILE = DeptProfile(
    code="in_xuong_d",
    name="In Xưởng D",
    icon="🖨️",
    prefix="IN_XUONG_D_DYNAMIC", # Sẽ được xử lý trong engine
    config_group="in_xuong_d",
    has_measurements=False,
    has_checklist=False,
    skip_bp=True, # Dòng 58 trong utils/ncr_helpers.py
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA",
    has_aql=False,
    phan_loai_options=["In", "Siêu Âm"]
)
