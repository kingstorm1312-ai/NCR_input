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
    smart_append_ncr,
    init_gspread,
    LIST_DON_VI_TINH,
    get_initial_status
)

# --- CẤU HÌNH TRANG ---
REQUIRED_DEPT = 'fi'
PAGE_TITLE = "QC Input - FI"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🔍", layout="centered")
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
        
        worksheet = sh.worksheet("CONFIG")
        df_config = pd.DataFrame(worksheet.get_all_records())
        
        list_noi_may = df_config['noi_may'].dropna().unique().tolist() if 'noi_may' in df_config.columns else []
        
        if 'nhom_loi' in df_config.columns:
            target_groups = ['may']
            list_loi = sorted(df_config[df_config['nhom_loi'].astype(str).str.strip().str.lower().isin(target_groups)]['ten_loi'].dropna().unique().tolist())
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
st.title(f"🔍 {PAGE_TITLE}")

# === PHẦN 1: THÔNG TIN PHIẾU (HEADER) ===
with st.expander("📝 Thông tin Phiếu", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    # Row 1: Số phiếu (NCR Suffix) & Số lần
    c1, c2 = st.columns(2)
    with c1:
        nguoi_lap = st.text_input("Người lập", value=user_info["name"], disabled=True)
    with c2:
        dept_prefix = "FI"
        current_month = get_now_vn().strftime("%m")
        ncr_suffix = st.text_input("Số đuôi NCR (xx)", help="Nhập 2 số cuối", disabled=disable_hd)
        so_phieu = ""
        if ncr_suffix:
            so_phieu = f"{dept_prefix}-{current_month}-{ncr_suffix}"
            st.caption(f"👉 Mã phiếu: **{so_phieu}**")

    # Row 2: Số lần & Tên SP
    r2_c1, r2_c2 = st.columns(2)
    with r2_c1:
        so_lan = st.number_input("Số lần", min_value=1, step=1, disabled=disable_hd, help="Số lần lặp lại")
    with r2_c2:
        ten_sp = st.text_input("Tên SP", disabled=disable_hd)

    # Row 3: Mã VT & Hợp đồng
    # Mã VT dùng text area cho thoải mái, nhưng để gọn layout ta để columns
    r3_c1, r3_c2 = st.columns(2)
    with r3_c1:
        raw_ma_vt = st.text_area("Mã VT (nhiều dòng)", height=68, disabled=disable_hd, help="Nhập nhiều mã cách nhau bằng dấu phẩy hoặc xuống dòng")
        # Normalize: Join lines/commas
        if raw_ma_vt:
            ma_vt = ", ".join([x.strip() for x in raw_ma_vt.replace('\n', ',').split(',') if x.strip()]).upper()
        else:
            ma_vt = ""
    with r3_c2:
        raw_hop_dong = st.text_input("Hợp đồng", disabled=disable_hd)
        hop_dong = format_contract_code(raw_hop_dong) if raw_hop_dong else ""

    # Row 4: SL Kiểm & SL Lô
    r4_c1, r4_c2 = st.columns(2)
    with r4_c1:
        sl_kiem = st.number_input("SL Kiểm", min_value=0, disabled=disable_hd)
    with r4_c2:
        sl_lo = st.number_input("SL Lô Hàng", min_value=0, disabled=disable_hd)

    # Row 5: ĐVT & Nguồn gốc
    r5_c1, r5_c2 = st.columns(2)
    with r5_c1:
        # Move DVT to Header
        don_vi_tinh = st.selectbox("Đơn vị tính", LIST_DON_VI_TINH, disabled=disable_hd)
    with r5_c2:
        nguon_goc_list = st.multiselect("Nguồn gốc (Nơi may)", LIST_NOI_MAY, disabled=disable_hd, placeholder="Chọn chuyền...")
        nguon_goc = ", ".join(nguon_goc_list)

    # Row 6: Mô tả lỗi (Last)
    # FI không phân loại cụ thể -> phan_loai = ""
    phan_loai = ""
    
    mo_ta_loi = st.text_area("Mô tả lỗi / Ghi chú", disabled=disable_hd, height=60)
    
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

# --- IMPORT AQL MANAGER ---
from utils.aql_manager import get_aql_standard, evaluate_lot_quality

# === PHẦN 1.2: THÔNG TIN AQL (TỰ ĐỘNG) ===
st.markdown("### 📊 Tiêu chuẩn AQL (Level II - 2.5/4.0)")
aql_info = get_aql_standard(sl_lo)
if aql_info:
    c_aql1, c_aql2, c_aql3, c_aql4 = st.columns(4)
    c_aql1.metric("Mã Chữ", aql_info['code'])
    c_aql2.metric("SL Mẫu", aql_info['sample_size'])
    c_aql3.metric("Lỗi Nặng (Ac/Re)", f"{aql_info['ac_major']} / {aql_info['ac_major']+1}")
    c_aql4.metric("Lỗi Nhẹ (Ac/Re)", f"{aql_info['ac_minor']} / {aql_info['ac_minor']+1}")
    
    # Auto-fill SL Kiem if empty or default
    if sl_kiem == 0:
        st.warning(f"💡 Gợi ý: Với lô {sl_lo}, bạn cần kiểm tra **{aql_info['sample_size']}** mẫu.")

else:
    st.info("Nhập 'SL Lô Hàng' để xem tiêu chuẩn AQL.")

# === PHẦN 1.5: KIỂM TRA ĐẶC BIỆT (SPECIAL INSPECTION) ===
with st.expander("📝 Bảng II: Kiểm tra Cấp độ đặc biệt", expanded=False):
    st.markdown("#### 1. Kích thước (Size)")
    c_sz1, c_sz2, c_sz3 = st.columns(3)
    with c_sz1:
        spec_size = st.text_input("Tiêu chuẩn (Size)", placeholder="VD: 20x30", disabled=st.session_state.header_locked)
    with c_sz2:
        tol_size = st.text_input("Dung sai (Size)", placeholder="VD: +/- 1cm", disabled=st.session_state.header_locked)
    with c_sz3:
        meas_size = st.text_area("Thực tế (Size)", placeholder="VD: 20, 21, 19.5...", help="Nhập các giá trị cách nhau bằng dấu phẩy hoặc xuống dòng", height=68, disabled=st.session_state.header_locked)

    st.divider()
    st.markdown("#### 2. Trọng lượng (Weight)")
    c_w1, c_w2, c_w3 = st.columns(3)
    with c_w1:
        spec_weight = st.text_input("Tiêu chuẩn (Weight)", placeholder="VD: 500g", disabled=st.session_state.header_locked)
    with c_w2:
        tol_weight = st.text_input("Dung sai (Weight)", placeholder="VD: +/- 5g", disabled=st.session_state.header_locked)
    with c_w3:
        meas_weight = st.text_area("Thực tế (Weight)", placeholder="VD: 501, 499, 500...", help="Nhập các giá trị cách nhau bằng dấu phẩy hoặc xuống dòng", height=68, disabled=st.session_state.header_locked)

    st.divider()
    st.markdown("#### 3. Checklist & Khác")
    c_ch1, c_ch2 = st.columns(2)
    with c_ch1:
        check_barcode = st.selectbox("Kiểm tra mã vạch", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
        check_weight_box = st.selectbox("Kiểm tra trọng lượng thùng", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    with c_ch2:
        check_print = st.selectbox("Nội dung in ấn", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
        check_color = st.selectbox("Màu sắc", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    
    check_other = st.text_area("Kiểm tra khác / Ghi chú đặc biệt", height=68, disabled=st.session_state.header_locked)

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
        sl_chon = st.number_input("SL Lỗi", min_value=1.0, step=0.1, format="%.1f", key="sl_existing")
    
    if selected_loi != "-- Chọn --":
        final_ten_loi = selected_loi
        final_so_luong = sl_chon
        default_muc_do = DICT_MUC_DO.get(final_ten_loi, "Nhẹ")

with tab_moi:
    new_loi = st.text_input("Tên lỗi mới")
    sl_new = st.number_input("SL Lỗi (Mới)", min_value=1.0, step=0.1, format="%.1f", key="sl_new")
        
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
            "sl_loi": final_so_luong,
            # don_vi_tinh is now in Header
        })
        st.toast(f"Đã thêm: {final_ten_loi}")

# === PHẦN 3: ĐÁNH GIÁ & LƯU ===
st.markdown("---")
st.markdown("### 🏆 Đánh giá & Lưu kết quả")

st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)

# Tính tổng lỗi
total_major = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] in ['Nặng', 'Nghiêm trọng']])
total_minor = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] == 'Nhẹ'])

# Đánh giá AQL
inspection_result, aql_details = evaluate_lot_quality(sl_lo, total_major, total_minor)

if inspection_result == 'Pass':
    st.success(f"✅ KẾT QUẢ: ĐẠT (PASS) - Không cần tạo NCR")
    save_label = "💾 LƯU BIÊN BẢN KIỂM TRA (Pass)"
    save_type = "primary"
    final_status = "Hoàn thành"
    final_ncr_num = "" # No NCR number for Pass
    
    # Logic Pass: Nếu không có lỗi nào được nhập, ta vẫn cần lưu 1 dòng 'dummy' để ghi nhận biên bản
    if not st.session_state.buffer_errors:
        st.info("ℹ️ Danh sách lỗi đang trống. Hệ thống sẽ lưu dòng 'Không có lỗi'.")

else:
    st.error(f"❌ KẾT QUẢ: KHÔNG ĐẠT (FAIL) - Cần tạo phiếu NCR")
    st.write(f"- Lỗi Nặng: {total_major} (Giới hạn: {aql_details.get('standard', {}).get('ac_major', 0)})")
    st.write(f"- Lỗi Nhẹ: {total_minor} (Giới hạn: {aql_details.get('standard', {}).get('ac_minor', 0)})")
    
    save_label = "🚨 LƯU & TẠO PHIẾU NCR (Fail)"
    save_type = "primary"
    final_status = get_initial_status(REQUIRED_DEPT)
    final_ncr_num = so_phieu # Use input NCR number

# Nút Lưu logic kép
if st.button(save_label, type=save_type, use_container_width=True):
    if inspection_result == 'Fail' and not final_ncr_num:
         st.error("⚠️ Vui lòng nhập Số đuôi NCR để tạo phiếu!")
         st.stop()
         
    try:
        with st.spinner("Đang lưu dữ liệu..."):
            hinh_anh_links = ""
            if uploaded_images:
                with st.spinner("Đang tải ảnh lên Cloud..."):
                    hinh_anh_links = upload_images_to_cloud(uploaded_images, final_ncr_num if final_ncr_num else "PASS_INSPECTION")
            
            sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
            ws = sh.worksheet("NCR_DATA")
            now = get_now_vn_str()
            
            # Chuẩn bị list lỗi để lưu
            errors_to_save = st.session_state.buffer_errors
            
            # Nếu Pass và không có lỗi, tạo 1 dòng dummy
            if inspection_result == 'Pass' and not errors_to_save:
                errors_to_save = [{
                    "ten_loi": "Không có lỗi",
                    "vi_tri": "",
                    "muc_do": "",
                    "sl_loi": 0
                }]
            
            success_count = 0
            for err in errors_to_save:
                data_to_save = {
                    'ngay_lap': now,
                    'so_phieu_ncr': final_ncr_num, # Empty if Pass
                    'so_lan': so_lan,
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
                    'trang_thai': final_status, # "Hoàn thành" if Pass
                    'thoi_gian_cap_nhat': now,
                    'hinh_anh': hinh_anh_links,
                    'don_vi_tinh': don_vi_tinh,
                    'ket_qua_kiem_tra': inspection_result, # Pass/Fail
                    # --- SPECIAL INSPECTION FIELDS ---
                    'spec_size': spec_size,
                    'tol_size': tol_size,
                    'meas_size': meas_size,
                    'spec_weight': spec_weight,
                    'tol_weight': tol_weight,
                    'meas_weight': meas_weight,
                    'check_barcode': check_barcode,
                    'check_weight_box': check_weight_box,
                    'check_print': check_print,
                    'check_color': check_color,
                    'check_other': check_other
                }
                if smart_append_ncr(ws, data_to_save):
                    success_count += 1
            
            if success_count > 0:
                st.success(f"✅ Đã lưu thành công! (Kết quả: {inspection_result})")
                st.balloons()
                st.session_state.buffer_errors = []
                st.session_state.header_locked = False
                # Optional: Rerun to clear form
                # st.rerun()
            else:
                st.warning("⚠️ Có lỗi khi lưu dữ liệu.")
                
    except Exception as e:
        st.error(f"❌ Lỗi hệ thống: {e}")
