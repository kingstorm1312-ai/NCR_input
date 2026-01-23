import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import sys
import os

# --- IMPORT UTILS (QUAN TRỌNG) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ncr_helpers import (
    get_now_vn, get_now_vn_str,
    format_contract_code, 
    render_input_buffer_mobile, 
    upload_images_to_cloud,
    smart_append_ncr
)

# --- CẤU HÌNH TRANG ---
REQUIRED_DEPT = 'may_n4'
PAGE_TITLE = "QC Input - May N4"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🧵", layout="centered")

# --- KIỂM TRA ĐĂNG NHẬP ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_dept = user_info.get("department")
user_role = user_info.get("role")

if user_role != 'admin' and user_dept != REQUIRED_DEPT:
    st.error(f"⛔ Bạn thuộc bộ phận '{user_dept}', không có quyền truy cập vào '{REQUIRED_DEPT}'!")
    if st.button("🔙 Quay lại trang chủ"):
        st.switch_page("Dashboard.py")
    st.stop()

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def init_gspread():
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        if isinstance(creds_str, str):
            creds_dict = json.loads(creds_str, strict=False)
        else:
            creds_dict = creds_str
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi khởi tạo gspread: {e}")
        return None

gc = init_gspread()

# --- TẢI DỮ LIỆU CẤU HÌNH (MASTER DATA) ---
@st.cache_data(ttl=600)
def load_master_data():
    try:
        if not gc: return [], [], [], {}
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        
        worksheet = sh.worksheet("CONFIG")
        df_config = pd.DataFrame(worksheet.get_all_records())
        
        list_noi_may = df_config['noi_may'].dropna().unique().tolist() if 'noi_may' in df_config.columns else []
        
        if 'nhom_loi' in df_config.columns:
            target_groups = ['may', 'chung']
            list_loi = sorted(df_config[df_config['nhom_loi'].astype(str).str.lower().isin(target_groups)]['ten_loi'].dropna().unique().tolist())
        else:
            list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist())

        list_vi_tri = df_config['vi_tri_loi'].dropna().unique().tolist() if 'vi_tri_loi' in df_config.columns else []
        dict_muc_do = df_config.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
        
        return list_noi_may, list_loi, list_vi_tri, dict_muc_do
        
    except Exception as e:
        st.error(f"Lỗi đọc Config: {e}")
        return [], [], [], {}

LIST_NOI_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data()

# --- QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
if "buffer_errors" not in st.session_state:
    st.session_state.buffer_errors = []
if "header_locked" not in st.session_state:
    st.session_state.header_locked = False

# --- GIAO DIỆN CHÍNH ---
st.title(f"🧵 {PAGE_TITLE}")

# === PHẦN 1: THÔNG TIN PHIẾU (HEADER) ===
with st.expander("📝 Thông tin Phiếu", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    c1, c2 = st.columns(2)
    with c1:
        nguoi_lap = st.text_input("Người lập", value=user_info["name"], disabled=True)
        dept_prefix = "MAY-N4"
        current_month = get_now_vn().strftime("%m")
        ncr_suffix = st.text_input("Số đuôi NCR (xx)", help="Nhập 2 số cuối", disabled=disable_hd)
        so_phieu = ""
        if ncr_suffix:
            so_phieu = f"{dept_prefix}-{current_month}-{ncr_suffix}"
            st.caption(f"👉 Mã phiếu: **{so_phieu}**")

    with c2:
        raw_ma_vt = st.text_input("Mã VT", disabled=disable_hd)
        ma_vt = raw_ma_vt.upper().strip() if raw_ma_vt else ""
        raw_hop_dong = st.text_input("Hợp đồng", disabled=disable_hd)
        hop_dong = format_contract_code(raw_hop_dong) if raw_hop_dong else ""

    c3, c4 = st.columns(2)
    with c3:
         sl_kiem = st.number_input("SL Kiểm", min_value=0, disabled=disable_hd)
         ten_sp = st.text_input("Tên SP", disabled=disable_hd)
    with c4:
         nguon_goc = st.selectbox("Chuyền / Tổ May", [""] + LIST_NOI_MAY, disabled=disable_hd)
         sl_lo = st.number_input("SL Lô", min_value=0, disabled=disable_hd)
    
    phan_loai = st.selectbox("Phân loại", ["", "Túi TP", "NPL"], disabled=disable_hd)
    mo_ta_loi = st.text_area("Ghi chú / Mô tả thêm", disabled=disable_hd, height=60)
    
    st.markdown("**📷 Hình ảnh:**")
    uploaded_images = st.file_uploader(
        "Chọn ảnh minh họa", 
        type=['png', 'jpg', 'jpeg'], 
        accept_multiple_files=True, 
        disabled=disable_hd
    )

    lock = st.checkbox("🔒 Khóa thông tin", value=st.session_state.header_locked)
    if lock != st.session_state.header_locked:
        st.session_state.header_locked = lock
        st.rerun()

# === PHẦN 2: CHI TIẾT LỖI ===
st.divider()
st.subheader("Chi tiết lỗi")

tab_chon, tab_moi = st.tabs(["Chọn từ danh sách", "Nhập lỗi mới"])

final_ten_loi = ""
final_so_luong = 1
default_muc_do = "Nhẹ"

with tab_chon:
    c_sel1, c_sel2 = st.columns([2, 1])
    with c_sel1:
        selected_loi = st.selectbox("Tên lỗi", ["-- Chọn --"] + LIST_LOI)
    with c_sel2:
        sl_chon = st.number_input("SL", min_value=1, key="sl_existing")
    
    if selected_loi != "-- Chọn --":
        final_ten_loi = selected_loi
        final_so_luong = sl_chon
        default_muc_do = DICT_MUC_DO.get(final_ten_loi, "Nhẹ")

with tab_moi:
    new_loi = st.text_input("Tên lỗi mới")
    sl_new = st.number_input("SL", min_value=1, key="sl_new")
    if new_loi:
        final_ten_loi = new_loi
        final_so_luong = sl_new

vi_tri = st.selectbox("Vị trí lỗi", LIST_VI_TRI if LIST_VI_TRI else [""])
if st.checkbox("Vị trí khác?"):
    vi_tri = st.text_input("Nhập vị trí cụ thể")

final_md_options = ["Nhẹ", "Nặng", "Nghiêm trọng"]
if default_muc_do not in final_md_options:
    default_muc_do = "Nhẹ"
final_md = st.pills("Mức độ", final_md_options, default=default_muc_do) or default_muc_do

if st.button("THÊM LỖI ⬇️", type="secondary", use_container_width=True):
    if not final_ten_loi or final_ten_loi == "-- Chọn --":
        st.error("Vui lòng chọn tên lỗi!")
    else:
        st.session_state.buffer_errors.append({
            "ten_loi": final_ten_loi,
            "vi_tri": vi_tri,
            "muc_do": final_md,
            "sl_loi": final_so_luong
        })
        st.toast(f"Đã thêm: {final_ten_loi}")

# === PHẦN 3: DANH SÁCH CHỜ & LƯU ===
st.markdown("### 📋 Danh sách lỗi chờ lưu")

if st.session_state.buffer_errors:
    st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)
    
    if st.button("💾 LƯU PHIẾU NCR", type="primary", use_container_width=True):
        if not so_phieu:
            st.error("⚠️ Chưa nhập số đuôi NCR!")
            st.stop()
            
        try:
            with st.spinner("Đang xử lý..."):
                hinh_anh_links = ""
                if uploaded_images:
                    with st.spinner("Đang tải ảnh lên Cloud..."):
                        hinh_anh_links = upload_images_to_cloud(uploaded_images, so_phieu)
                
                sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                ws = sh.worksheet("NCR_DATA")
                now = get_now_vn_str()
                
                success_count = 0
                for err in st.session_state.buffer_errors:
                    data_to_save = {
                        'ngay_lap': now,
                        'so_phieu_ncr': so_phieu,
                        'hop_dong': hop_dong,
                        'ma_vat_tu': ma_vt,
                        'ten_sp': ten_sp,
                        'phan_loai': phan_loai,
                        'nguon_goc': nguon_goc,
                        'ten_loi': err['ten_loi'],
                        'vi_tri_loi': err['vi_tri'],
                        'so_luong_loi': err['sl_loi'],
                        'so_luong_kiem': sl_kiem,
                        'muc_do': err['muc_do'],
                        'mo_ta_loi': mo_ta_loi,
                        'so_luong_lo_hang': sl_lo,
                        'nguoi_lap_phieu': nguoi_lap,
                        'noi_gay_loi': nguon_goc,
                        'trang_thai': 'cho_truong_ca',
                        'thoi_gian_cap_nhat': now,
                        'hinh_anh': hinh_anh_links
                    }
                    if smart_append_ncr(ws, data_to_save):
                        success_count += 1
                
                if success_count == len(st.session_state.buffer_errors):
                    st.success(f"✅ Đã lưu thành công {success_count} dòng lỗi!")
                    st.balloons()
                    st.session_state.buffer_errors = []
                    st.session_state.header_locked = False
                else:
                    st.warning(f"⚠️ Chỉ lưu được {success_count}/{len(st.session_state.buffer_errors)} dòng.")
        except Exception as e:
            st.error(f"❌ Lỗi hệ thống: {e}")
