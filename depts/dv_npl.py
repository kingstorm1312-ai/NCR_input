from core.profile import DeptProfile
import streamlit as st

# Profile cho bộ phận ĐV NPL
# Trích xuất từ pages/03_dv_npl.py
PROFILE = DeptProfile(
    code="dv_npl",
    name="ĐV NPL",
    icon="📦",
    prefix="DVNPL", # NCR_DEPARTMENT_PREFIXES["DV_NPL"]
    config_group="dv_npl",
    has_measurements=False,
    has_checklist=False,
    skip_bp=True, # Dòng 53 trong utils/ncr_helpers.py
    sheet_spreadsheet_id=st.secrets["connections"]["gsheets"]["spreadsheet"],
    sheet_worksheet_name="NCR_DATA",
    has_aql=False,
    phan_loai_options=[
        "", "BXD", "Chỉ", "Cuộn foam", "Cuộn lưới", "Cuộn VKD", "Dây đai", "Dây dù", 
        "Dây kéo, đầu kéo", "Dây viền", "Dây rút", "Dây nẹp", "Đế nhựa", "Giấy carton", 
        "Túi giấy", "Giấy tấm pallet", "Dây thun", "Dây Thừng", "Cuộn in", "Khay", 
        "Hộp", "Manh", "Nắp", "Nẹp", "Nhựa", "Nút", "Ống nhựa", "Tấm lót", 
        "Tấm nhựa", "Tem", "Thùng", "Túi poly", "Túi pp"
    ]
)
