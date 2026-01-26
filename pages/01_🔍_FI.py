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
from utils.aql_manager import get_aql_standard, evaluate_lot_quality

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
if "custom_sample_size" not in st.session_state:
    st.session_state.custom_sample_size = False # Toggle để sửa SL Mẫu

# --- GIAO DIỆN CHÍNH ---
st.title(f"🔍 {PAGE_TITLE}")

# === PHẦN 1: THIẾT LẬP KIỂM TRA (TOP SECTION)
# ==========================================
st.subheader("1️⃣ Thiết lập kiểm tra")

# Row 1: SL Lô & SL Mẫu (Quan trọng nhất)
c_sl1, c_sl2 = st.columns([1, 1])
with c_sl1:
    sl_lo = st.number_input("📦 SL Lô Hàng", min_value=0, disabled=st.session_state.header_locked)

# Tính toán AQL tự động
aql_info = get_aql_standard(sl_lo)
calc_sample_size = 0
if aql_info:
    calc_sample_size = aql_info['sample_size']

with c_sl2:
    # Logic Toggle sửa SL Mẫu
    col_inp, col_tog = st.columns([0.8, 0.2])
    with col_tog:
        st.write("") # Spacer align
        st.write("") 
        is_custom = st.checkbox("🔓", value=st.session_state.custom_sample_size, help="Mở khóa để sửa SL Mẫu", key="chk_custom_sample")
        st.session_state.custom_sample_size = is_custom
    
    with col_inp:
        if st.session_state.custom_sample_size:
             sl_kiem = st.number_input("SL Mẫu (Tùy chỉnh)", min_value=0, value=calc_sample_size, disabled=st.session_state.header_locked)
        else:
             sl_kiem = st.number_input("SL Mẫu (AQL)", value=calc_sample_size, disabled=True, help="Tự động tính theo AQL Level II")

# Hiển thị thông tin AQL
if aql_info:
    st.info(f"📊 **AQL Level II**: Mã **{aql_info['code']}** | Giới hạn: Nặng **{aql_info['ac_major']}/{aql_info['ac_major']+1}** - Nhẹ **{aql_info['ac_minor']}/{aql_info['ac_minor']+1}**", icon="ℹ️")

# Row 2: Thông tin định danh (Gom nhóm gọn lại)
with st.expander("📝 Thông tin chi tiết (SP, HĐ, Nguồn gốc...)", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    # 3 CỘT INPUT MỚI (NEW FIELDS)
    col_new1, col_new2, col_new3 = st.columns(3)
    with col_new1:
        so_po = st.text_input("Số PO", placeholder="VD: 4500123456", disabled=disable_hd)
    with col_new2:
        don_vi_kiem = st.text_input("Đơn vị kiểm", value="", placeholder="Nhập đơn vị kiểm...", disabled=disable_hd)
    with col_new3:
        # Khách hàng auto từ Hợp đồng (3 ký tự cuối)
        # Sẽ xử lý logic hiển thị
        khach_hang_preview = ""
    
    st.divider()
    
    # Tên SP & Hợp đồng
    r2_c1, r2_c2 = st.columns(2)
    with r2_c1:
        ten_sp = st.text_input("Tên SP", disabled=disable_hd)
    with r2_c2:
        raw_hop_dong = st.text_input("Hợp đồng", disabled=disable_hd)
        hop_dong = format_contract_code(raw_hop_dong) if raw_hop_dong else ""
        
        # Logic tách khách hàng
        khach_hang = ""
        if hop_dong and len(hop_dong) >= 3:
            # Lấy 3 ký tự cuối, loại bỏ số sau cùng nếu format là ABC-123-XYZ-01
            # Tuy nhiên rule đơn giản nhất là lấy 3 ký tự chữ cái cuối cùng của chuỗi contract code chuẩn
            parts = hop_dong.split('-')
            # Thường format: 50A-24-SH-01 -> SH ?
            # User request: "Khách hàng sẽ là 3 ký tự chữ cuối của số hợp đồng"
            # Ta sẽ lấy cụm chữ cái cuối cùng.
            potential_cust = parts[-1] if not parts[-1].isdigit() else (parts[-2] if len(parts) > 1 else "")
            # Lọc chỉ lấy chữ
            khach_hang = ''.join(filter(str.isalpha, potential_cust))
            if not khach_hang and len(parts) >= 2:
                 khach_hang = ''.join(filter(str.isalpha, parts[-2]))
            
            # Simple fallback if complex parsing fails: Last 3 chars
            if not khach_hang:
                khach_hang = hop_dong[-3:]
            
            st.caption(f"👉 Khách hàng (Tự động): **{khach_hang}**")

    # Mã VT & Số lần
    r3_c1, r3_c2 = st.columns(2)
    with r3_c1:
        raw_ma_vt = st.text_area("Mã VT", height=68, disabled=disable_hd, placeholder="Nhiều mã cách nhau bởi dấu phẩy")
        if raw_ma_vt:
            ma_vt = ", ".join([x.strip() for x in raw_ma_vt.replace('\n', ',').split(',') if x.strip()]).upper()
        else:
            ma_vt = ""
    with r3_c2:
        so_lan = st.number_input("Số lần kiểm", min_value=1, step=1, disabled=disable_hd)
        don_vi_tinh = st.selectbox("Đơn vị tính", LIST_DON_VI_TINH, disabled=disable_hd)

    # Nguồn gốc
    nguon_goc_list = st.multiselect("Nguồn gốc (Chuyền/NCC)", LIST_NOI_MAY, disabled=disable_hd)
    nguon_goc = ", ".join(nguon_goc_list)

    # Lock Toggle
    lock = st.checkbox("🔒 Khóa thông tin chung", value=st.session_state.header_locked)
    if lock != st.session_state.header_locked:
        st.session_state.header_locked = lock
        st.rerun()

# ==========================================
# PHẦN 2: NHẬP KẾT QUẢ (BODY SECTION)
# ==========================================
st.markdown("---")
st.subheader("2️⃣ Kết quả kiểm tra")

# Tabbed Interface
tab_measure, tab_defects = st.tabs(["📏 Đo đạc & Checklist", "🐞 Chi tiết Lỗi"])

with tab_measure:
    st.markdown("**1. Kích thước (Size)**")
    c_sz1, c_sz2, c_sz3 = st.columns(3)
    spec_size = c_sz1.text_input("Tiêu chuẩn (Size)", placeholder="VD: 20x30", disabled=st.session_state.header_locked)
    tol_size = c_sz2.text_input("Dung sai (Size)", placeholder="VD: +/- 1cm", disabled=st.session_state.header_locked)
    meas_size = c_sz3.text_area("Thực tế (Size)", placeholder="VD: 20, 21...", height=68, disabled=st.session_state.header_locked)

    st.markdown("**2. Trọng lượng (Weight)**")
    c_w1, c_w2, c_w3 = st.columns(3)
    spec_weight = c_w1.text_input("Tiêu chuẩn (Weight)", placeholder="VD: 500g", disabled=st.session_state.header_locked)
    tol_weight = c_w2.text_input("Dung sai (Weight)", placeholder="VD: +/- 5g", disabled=st.session_state.header_locked)
    meas_weight = c_w3.text_area("Thực tế (Weight)", placeholder="VD: 501, 499...", height=68, disabled=st.session_state.header_locked)

    st.markdown("**3. Checklist**")
    c_ch1, c_ch2 = st.columns(2)
    check_barcode = c_ch1.selectbox("Mã vạch", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    check_weight_box = c_ch1.selectbox("Cân thùng", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    check_print = c_ch2.selectbox("In ấn", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    check_color = c_ch2.selectbox("Màu sắc", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
    check_other = st.text_area("Ghi chú khác", height=68, disabled=st.session_state.header_locked)

with tab_defects:
    # Add Defect Form
    c_def1, c_def2 = st.columns([2, 1])
    selected_loi = c_def1.selectbox("Chọn Tên lỗi", ["-- Chọn --"] + LIST_LOI)
    
    # Input mới nếu không có trong list
    final_ten_loi = selected_loi
    if selected_loi == "-- Chọn --":
        new_loi = st.text_input("...hoặc Nhập tên lỗi mới")
        if new_loi: final_ten_loi = new_loi
    else:
        # Auto fill muc do
        default_md = DICT_MUC_DO.get(selected_loi, "Nhẹ")
    
    sl_loi_input = c_def2.number_input("SL Lỗi", min_value=1.0, step=1.0)
    
    # M?c ?? & V? trí
    c_extra1, c_extra2 = st.columns(2)
    
    final_md_options = ["Nhẹ", "Nặng", "Nghiêm trọng"]
    final_md = c_extra1.pills("Mức độ", final_md_options, default="Nhẹ")
    vi_tri = c_extra2.selectbox("Vị trí", [""] + LIST_VI_TRI)
    if not vi_tri: vi_tri = c_extra2.text_input("Vị trí khác", placeholder="Nhập vị trí...")

    if st.button("➕ THÊM LỖI VÀO DANH SÁCH", use_container_width=True):
        if not final_ten_loi or final_ten_loi == "-- Chọn --":
            st.error("Chưa chọn tên lỗi!")
        else:
            st.session_state.buffer_errors.append({
                "ten_loi": final_ten_loi,
                "vi_tri": vi_tri,
                "muc_do": final_md,
                "sl_loi": sl_loi_input
            })
            st.toast(f"Đã thêm: {final_ten_loi}")

    # List Errors
    if st.session_state.buffer_errors:
        st.markdown("##### Danh sách đã nhập:")
        st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)

# ==========================================
# PHẦN 3: KẾT LUẬN & XỬ LÝ (ACTION SECTION)
# ==========================================
st.markdown("---")
st.subheader("3️⃣ Kết luận & Xử lý")

# Tính toán kết quả
total_major = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] in ['Nặng', 'Nghiêm trọng']])
total_minor = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] == 'Nhẹ'])

inspection_result, aql_details = evaluate_lot_quality(sl_lo, total_major, total_minor)

# Layout Conditional (Pass vs Fail)
final_ncr_num = ""
mo_ta_loi = ""
uploaded_images = []

if inspection_result == 'Pass':
    # === TRƯỜNG HỢP PASS ===
    st.success("✅ **KẾT QUẢ: ĐẠT (PASS)** - Đủ điều kiện nhập kho!")
    
    # Optional logic: Nếu Checkbox Checklist Fail -> Warn?
    # Logic hiện tại: Chỉ dựa vào AQL Lỗi.
    
    if not st.session_state.buffer_errors:
        st.caption("ℹ️ Không phát hiện lỗi nào.")
        
    save_label = "💾 LƯU BIÊN BẢN KIỂM TRA (PASS)"
    save_btn_type = "primary"
    
else:
    # === TRƯỜNG HỢP FAIL ===
    st.error("❌ **KẾT QUẢ: KHÔNG ĐẠT (FAIL)** - Cần lập phiếu NCR!")
    
    # Hiển thị thống kê
    limit_major = aql_details.get('standard', {}).get('ac_major', 0)
    limit_minor = aql_details.get('standard', {}).get('ac_minor', 0)
    
    c_stat1, c_stat2 = st.columns(2)
    c_stat1.metric("Lỗi Nặng (Major)", f"{total_major}", delta=f"Giới hạn: {limit_major}", delta_color="inverse")
    c_stat2.metric("Lỗi Nhẹ (Minor)", f"{total_minor}", delta=f"Giới hạn: {limit_minor}", delta_color="inverse")
    
    st.markdown("#### 📝 Thông tin NCR bổ sung")
    
    # NCR Number Input (Only for Fail)
    dept_prefix = "FI"
    curr_month = get_now_vn().strftime("%m")
    c_ncr1, c_ncr2 = st.columns([1, 2])
    ncr_suffix = c_ncr1.text_input("Số đuôi NCR (xx)", help="Nhập 2 số cuối của phiếu", max_chars=3)
    if ncr_suffix:
        final_ncr_num = f"{dept_prefix}-{curr_month}-{ncr_suffix}"
        c_ncr2.markdown(f"👉 Mã phiếu: **{final_ncr_num}**")
    else:
        c_ncr2.warning("⬅️ Vui lòng nhập số đuôi phiếu NCR")
        
    mo_ta_loi = st.text_area("Mô tả lỗi chi tiết / Nguyên nhân", height=80)
    uploaded_images = st.file_uploader("Hình ảnh bằng chứng", type=['jpg', 'png'], accept_multiple_files=True)
    
    save_label = "🚨 LƯU & TẠO PHIẾU NCR"
    save_btn_type = "primary"

# --- NÚT LƯU CUỐI CÙNG ---
if st.button(save_label, type=save_btn_type, use_container_width=True):
    # Validation
    if inspection_result == 'Fail' and not final_ncr_num:
        st.error("⚠️ Vui lòng nhập SỐ ĐUÔI NCR trước khi lưu!")
        st.stop()
    
    try:
        with st.spinner("Đang lưu dữ liệu hệ thống..."):
            # Upload ảnh nếu có
            if uploaded_images:
                img_links = upload_images_to_cloud(uploaded_images, final_ncr_num if final_ncr_num else "PASS_REC")
            else:
                img_links = ""
                
            sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
            ws = sh.worksheet("NCR_DATA")
            now = get_now_vn_str()
            
            # Prepare Data List
            # Nếu Pass mà ko có lỗi -> Tạo 1 dummy record
            records_to_save = st.session_state.buffer_errors
            if inspection_result == 'Pass' and not records_to_save:
                records_to_save = [{
                    "ten_loi": "Không có lỗi", "vi_tri": "", "muc_do": "", "sl_loi": 0
                }]
                
            success_count = 0
            # Define Status
            current_status = "Hoàn thành" if inspection_result == 'Pass' else get_initial_status(REQUIRED_DEPT)
            
            for err in records_to_save:
                row_data = {
                    'ngay_lap': now,
                    'so_phieu_ncr': final_ncr_num, # Empty if Pass
                    'so_lan': so_lan,
                    'hop_dong': hop_dong,
                    'ma_vat_tu': ma_vt,
                    'ten_sp': ten_sp,
                    'phan_loai': "", # FI no class
                    'nguon_goc': nguon_goc,
                    'ten_loi': err['ten_loi'],
                    'vi_tri_loi': err['vi_tri'],
                    'so_luong_loi': err['sl_loi'],
                    'so_luong_kiem': sl_kiem,
                    'muc_do': err['muc_do'],
                    'mo_ta_loi': mo_ta_loi, # Only Fail has notes
                    'so_luong_lo_hang': sl_lo,
                    'nguoi_lap_phieu': user_info.get("name"),
                    'noi_gay_loi': nguon_goc,
                    'trang_thai': current_status,
                    'thoi_gian_cap_nhat': now,
                    'hinh_anh': img_links,
                    'don_vi_tinh': don_vi_tinh,
                    'ket_qua_kiem_tra': inspection_result,
                    # Special Fields
                    'spec_size': spec_size, 'tol_size': tol_size, 'meas_size': meas_size,
                    'spec_weight': spec_weight, 'tol_weight': tol_weight, 'meas_weight': meas_weight,
                    'check_barcode': check_barcode, 'check_weight_box': check_weight_box,
                    'check_print': check_print, 'check_color': check_color, 'check_other': check_other,
                    # NEW FIELDS
                    'so_po': so_po,
                    'khach_hang': khach_hang,
                    'don_vi_kiem': don_vi_kiem
                }
                if smart_append_ncr(ws, row_data):
                    success_count += 1
            
            if success_count > 0:
                st.balloons()
                st.success(f"✅ Đã lưu thành công! ({inspection_result})")
                
                # Clear state
                st.session_state.buffer_errors = []
                st.session_state.header_locked = False
                # st.rerun() # Optional
            else:
                st.error("Lỗi khi lưu dữ liệu vào Sheet.")
                
    except Exception as e:
        st.error(f"System Error: {e}")
