import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import sys
import os

# --- IMPORT UTILS (QUAN TRỌNG) ---
# Thêm đường dẫn để import được từ thư mục cha
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import các hàm chung đã được tối ưu
from utils.ncr_helpers import (
    init_gspread,
    get_now_vn, get_now_vn_str,
    format_contract_code, 
    render_input_buffer_mobile, 
    upload_images_to_cloud,
    smart_append_ncr,
    LIST_DON_VI_TINH,
    get_initial_status
)
from utils.aql_manager import get_aql_standard

# --- CẤU HÌNH TRANG ---
REQUIRED_DEPT = 'may_i'
PAGE_TITLE = "QC Input - May I"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🧵", layout="centered")
# --- MOBILE NAVIGATION HELPER ---
st.markdown("""
<style>
    /* Đảm bảo header và nút sidebar rõ ràng trên di động */
    header[data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        z-index: 999999;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧭 Điều hướng")
    if st.button("🏠 Về Trang Chủ", use_container_width=True):
        st.switch_page("Dashboard.py")
    st.divider()


# --- KIỂM TRA ĐĂNG NHẬP ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_dept = user_info.get("department")
user_role = user_info.get("role")

# Chỉ cho phép Admin hoặc đúng bộ phận truy cập
if user_role != 'admin' and user_dept != REQUIRED_DEPT:
    st.error(f"⛔ Bạn thuộc bộ phận '{user_dept}', không có quyền truy cập vào '{REQUIRED_DEPT}'!")
    if st.button("🔙 Quay lại trang chủ"):
        st.switch_page("Dashboard.py")
    st.stop()

# --- KẾT NỐI GOOGLE SHEETS ---

gc = init_gspread()

# --- TẢI DỮ LIỆU CẤU HÌNH (MASTER DATA) ---
@st.cache_data(ttl=600)
def load_master_data():
    try:
        if not gc: return [], [], [], {}
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        
        # Đọc sheet CONFIG
        worksheet = sh.worksheet("CONFIG")
        df_config = pd.DataFrame(worksheet.get_all_records())
        
        # Lấy danh sách Nguồn gốc (Nơi may)
        list_noi_may = df_config['noi_may'].dropna().unique().tolist() if 'noi_may' in df_config.columns else []
        
        # Lấy danh sách Lỗi (Lọc theo nhóm 'may' hoặc 'chung')
        if 'nhom_loi' in df_config.columns:
            target_groups = ['may']
            list_loi = sorted(df_config[df_config['nhom_loi'].astype(str).str.strip().str.lower().isin(target_groups)]['ten_loi'].dropna().unique().tolist())
        else:
            list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist())

        # Lấy danh sách Vị trí & Mức độ
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
st.title("🧵 QC Input - May I")

# === PHẦN 1: THÔNG TIN PHIẾU (HEADER) ===
with st.expander("📝 Thông tin Phiếu", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    # Hàng 1: User | Suffix
    c1, c2 = st.columns(2)
    with c1:
        nguoi_lap = st.text_input("Người lập", value=user_info["name"], disabled=True)
    with c2:
        dept_prefix = "I'"
        current_month = get_now_vn().strftime("%m")
        ncr_suffix = st.text_input("Số đuôi NCR (xx)", help="Nhập 2 số cuối", disabled=disable_hd)
        so_phieu = ""
        if ncr_suffix:
            so_phieu = f"{dept_prefix}-{current_month}-{ncr_suffix}"
            st.caption(f"👉 Mã phiếu: **{so_phieu}**")

    # Hàng 2: Số lần | Tên SP
    r2_c1, r2_c2 = st.columns(2)
    with r2_c1:
        so_lan = st.number_input("Số lần", min_value=1, step=1, disabled=disable_hd)
    with r2_c2:
        ten_sp = st.text_input("Tên SP", disabled=disable_hd)

    # Hàng 3: Mã VT | Hợp đồng
    r3_c1, r3_c2 = st.columns(2)
    with r3_c1:
        raw_ma_vt = st.text_input("Mã VT", disabled=disable_hd)
        ma_vt = raw_ma_vt.upper().strip() if raw_ma_vt else ""
    with r3_c2:
        raw_hop_dong = st.text_input("Hợp đồng", disabled=disable_hd)
        hop_dong = format_contract_code(raw_hop_dong) if raw_hop_dong else ""
        
        # Logic tách khách hàng (tương tự FI)
        khach_hang = ""
        if hop_dong and len(hop_dong) >= 3:
            parts = hop_dong.split('-')
            potential_cust = parts[-1] if not parts[-1].isdigit() else (parts[-2] if len(parts) > 1 else "")
            khach_hang = ''.join(filter(str.isalpha, potential_cust))
            if not khach_hang and len(parts) >= 2:
                 khach_hang = ''.join(filter(str.isalpha, parts[-2]))
            if not khach_hang:
                khach_hang = hop_dong[-3:]
            st.caption(f"👉 KH: **{khach_hang}**")

    # Hàng 3.5: PO | Đơn vị kiểm
    r35_c1, r35_c2 = st.columns(2)
    with r35_c1:
        so_po = st.text_input("Số PO", placeholder="VD: 4500...", disabled=disable_hd)
    with r35_c2:
        don_vi_kiem = st.text_input("Đơn vị kiểm", value="", placeholder="Nhập ĐV kiểm...", disabled=disable_hd)

    # Hàng 4: SL Kiểm | SL Lô
    r4_c1, r4_c2 = st.columns(2)
    with r4_c1:
         sl_kiem = st.number_input("SL Kiểm", min_value=0, disabled=disable_hd)
    with r4_c2:
         sl_lo = st.number_input("SL Lô", min_value=0, disabled=disable_hd)
         
         # AQL Calculation
         ac_major, ac_minor, sample_size, aql_code = "", "", "", ""
         if sl_lo > 0:
            aql_info = get_aql_standard(sl_lo)
            if aql_info:
                st.info(f"📊 AQL **{aql_info['code']}** | Mẫu: **{aql_info['sample_size']}** | Major: **{aql_info['ac_major']}** | Minor: **{aql_info['ac_minor']}**", icon="ℹ️")
                ac_major = aql_info['ac_major']
                ac_minor = aql_info['ac_minor']
                sample_size = aql_info['sample_size']
                aql_code = aql_info['code']
    
    # Hàng 5: ĐVT | Nguồn gốc
    r5_c1, r5_c2 = st.columns(2)
    with r5_c1:
        don_vi_tinh = st.selectbox("Đơn vị tính", LIST_DON_VI_TINH, disabled=disable_hd)
    with r5_c2:
         nguon_goc = st.selectbox("Chuyền / Tổ May", [""] + LIST_NOI_MAY, disabled=disable_hd)

    # Các trường khác
    phan_loai = st.selectbox("Phân loại", ["", "Túi TP", "NPL"], disabled=disable_hd)
    mo_ta_loi = st.text_area("Ghi chú / Mô tả thêm", disabled=disable_hd, height=60)
    
    # Upload ảnh (Cloudinary)
    st.markdown("**📷 Hình ảnh:**")
    uploaded_images = st.file_uploader(
        "Chọn ảnh minh họa", 
        type=['png', 'jpg', 'jpeg'], 
        accept_multiple_files=True, 
        disabled=disable_hd
    )

    # Nút khóa
    lock = st.checkbox("🔒 Khóa thông tin", value=st.session_state.header_locked)
    if lock != st.session_state.header_locked:
        st.session_state.header_locked = lock
        st.rerun()

# === PHẦN 2: CHI TIẾT LỖI ===
st.divider()
st.subheader("Chi tiết lỗi")

# Lock Toggle Check
if "inp_ten_loi" not in st.session_state: st.session_state["inp_ten_loi"] = "-- Chọn --"
if "inp_ten_loi_moi" not in st.session_state: st.session_state["inp_ten_loi_moi"] = ""

# Toggle Input Mode
mode_input = st.radio("Chế độ nhập:", ["Chọn từ danh sách", "Nhập mới"], horizontal=True, key="radio_mode")

c_def1, c_def2 = st.columns([2, 1])

if mode_input == "Chọn từ danh sách":
    c_def1.selectbox("Chọn Tên lỗi", ["-- Chọn --"] + LIST_LOI, key="inp_ten_loi")
else:
    c_def1.text_input("Nhập tên lỗi mới", key="inp_ten_loi_moi")

# SL & DVT
with c_def2:
    sl_loi_input = st.number_input("SL Lỗi", min_value=1.0, step=0.1, format="%.1f", key="inp_sl_loi")

c_def3, c_def4 = st.columns(2)
with c_def3:
    dvt_input = st.selectbox("ĐVT", LIST_DON_VI_TINH, key="inp_dvt")

# Position & Severity
vi_tri_sel = c_def4.selectbox("Vị trí", [""] + LIST_VI_TRI, key="inp_vi_tri_sel")

# Allow manual position if select is empty or user wants strict control? 
# Current flow in FI uses text input if select is empty. adopting that.
vi_tri_txt = ""
if not vi_tri_sel:
    vi_tri_txt = st.text_input("Vị trí khác", placeholder="Nhập vị trí...", key="inp_vi_tri_txt")

md_opts = ["Nhẹ", "Nặng", "Nghiêm trọng"]
st.pills("Mức độ", md_opts, default="Nhẹ", key="inp_muc_do")

def add_defect_callback():
    mode = st.session_state.get("radio_mode", "Chọn từ danh sách")
    final_name = ""
    if mode == "Chọn từ danh sách":
        s_loi = st.session_state.get("inp_ten_loi", "-- Chọn --")
        if s_loi == "-- Chọn --":
            st.session_state["add_err_msg"] = "⚠️ Chưa chọn tên lỗi!"
            return
        final_name = s_loi
    else:
        s_loi_moi = st.session_state.get("inp_ten_loi_moi", "").strip()
        if not s_loi_moi:
            st.session_state["add_err_msg"] = "⚠️ Chưa nhập tên lỗi mới!"
            return
        final_name = s_loi_moi
        
    s_qty = st.session_state.get("inp_sl_loi", 1.0)
    s_dvt = st.session_state.get("inp_dvt", "Chiếc")
    s_pos = st.session_state.get("inp_vi_tri_sel", "") or st.session_state.get("inp_vi_tri_txt", "").strip()
    s_sev = st.session_state.get("inp_muc_do", "Nhẹ")
    
    st.session_state.buffer_errors.append({
        "ten_loi": final_name,
        "vi_tri": s_pos,
        "muc_do": s_sev,
        "sl_loi": s_qty,
        "don_vi_tinh": s_dvt
    })
    st.session_state["success_msg"] = f"Đã thêm: {final_name}"
    st.session_state["add_err_msg"] = ""
    
    # Reset
    st.session_state["inp_ten_loi"] = "-- Chọn --"
    st.session_state["inp_ten_loi_moi"] = ""
    st.session_state["inp_sl_loi"] = 1.0
    st.session_state["inp_vi_tri_sel"] = ""
    st.session_state["inp_vi_tri_txt"] = ""
    st.session_state["inp_muc_do"] = "Nhẹ"

st.button("➕ THÊM LỖI VÀO DANH SÁCH", use_container_width=True, on_click=add_defect_callback)

if st.session_state.get("add_err_msg"):
    st.error(st.session_state["add_err_msg"])
    st.session_state["add_err_msg"] = "" 
    
if st.session_state.get("success_msg"):
    st.toast(st.session_state["success_msg"])
    st.session_state["success_msg"] = ""

# === PHẦN 3: DANH SÁCH CHỜ & LƯU ===
st.markdown("### 📋 Danh sách lỗi chờ lưu")

if st.session_state.buffer_errors:
    # Hiển thị bảng buffer (Dùng hàm từ Utils để code gọn)
    st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)

# Nút Lưu Chính Thức
if st.button("💾 LƯU PHIẾU NCR", type="primary", use_container_width=True):
    if not so_phieu:
        st.error("⚠️ Chưa nhập số đuôi NCR!")
        st.stop()
        
    try:
        with st.spinner("Đang xử lý..."):
            # 1. Upload ảnh lên Cloudinary
            hinh_anh_links = ""
            if uploaded_images:
                with st.spinner("Đang tải ảnh lên Cloud..."):
                    hinh_anh_links = upload_images_to_cloud(uploaded_images, so_phieu)
            
            # 2. Kết nối Sheet
            sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
            ws = sh.worksheet("NCR_DATA")
            now = get_now_vn_str()
            
            # 3. Duyệt qua từng lỗi trong Buffer và Lưu
            success_count = 0
            for err in st.session_state.buffer_errors:
                # Tạo Dictionary dữ liệu (Key phải khớp với Header trên Sheet)
                data_to_save = {
                    'ngay_lap': now,
                    'so_phieu_ncr': so_phieu,
                    'so_lan': so_lan,
                    'hop_dong': hop_dong,
                    'ma_vat_tu': ma_vt,
                    'ten_sp': ten_sp,
                    'phan_loai': phan_loai,
                    'nguon_goc': nguon_goc,  # Cột quan trọng
                    'ten_loi': err['ten_loi'],
                    'vi_tri_loi': err['vi_tri'],
                    'so_luong_loi': err['sl_loi'],
                    'so_luong_kiem': sl_kiem,
                    'muc_do': err['muc_do'],
                    'mo_ta_loi': mo_ta_loi,
                    'so_luong_lo_hang': sl_lo,
                    'nguoi_lap_phieu': nguoi_lap,
                    'noi_gay_loi': nguon_goc,
                    'trang_thai': get_initial_status(REQUIRED_DEPT),
                    'thoi_gian_cap_nhat': now,
                    'hinh_anh': hinh_anh_links,
                    'don_vi_tinh': don_vi_tinh,
                    # New Fields
                    'so_po': so_po,
                    'khach_hang': khach_hang,
                    'don_vi_kiem': don_vi_kiem,
                    'sample_size': sample_size,
                    'aql_code': aql_code,
                    'ac_major': ac_major,
                    'ac_minor': ac_minor
                }
                
                # Dùng hàm lưu thông minh (không lo lệch cột)
                if smart_append_ncr(ws, data_to_save):
                    success_count += 1
            
            if success_count == len(st.session_state.buffer_errors):
                st.success(f"✅ Đã lưu thành công {success_count} dòng lỗi!")
                st.balloons()
                # Xóa buffer và reset form
                st.session_state.buffer_errors = []
                st.session_state.header_locked = False
                # st.rerun() # Tự động reload nếu cần
            else:
                st.warning(f"⚠️ Chỉ lưu được {success_count}/{len(st.session_state.buffer_errors)} dòng. Vui lòng kiểm tra lại.")
            
    except Exception as e:
        st.error(f"❌ Lỗi hệ thống: {e}")