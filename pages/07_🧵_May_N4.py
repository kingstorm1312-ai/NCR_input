import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import sys
import os

# Add root to path for utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import format_contract_code, render_input_buffer_mobile, upload_images_to_drive

# --- CONFIGURATION ---
REQUIRED_DEPT = 'may_n4'
PAGE_TITLE = "QC Input - May N4"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🏭", layout="centered")

# --- SECURITY CHECK (CRITICAL) ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_dept = user_info.get("department")
user_role = user_info.get("role")

# Allow access if Admin OR if Department matches exactly
if user_role != 'admin' and user_dept != REQUIRED_DEPT:
    st.error(f"⛔ Bạn thuộc bộ phận '{user_dept}', không có quyền truy cập vào '{REQUIRED_DEPT}'!")
    if st.button("🔙 Quay lại trang chủ"):
        st.switch_page("Dashboard.py")
    st.stop()

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def init_gspread():
    """Khởi tạo gspread client từ secrets"""
    try:
        # Lấy service account credentials từ secrets
        # Vì trong TOML để là string triple quotes nên cần parse JSON
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        
        if isinstance(creds_str, str):
            # strict=False allows control characters (newlines) inside strings
            credentials_dict = json.loads(creds_str, strict=False)
        else:
            credentials_dict = creds_str
            
        # Tạo credentials object và authorize
        gc = gspread.service_account_from_dict(credentials_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi khởi tạo gspread: {e}")
        return None

# Khởi tạo client
gc = init_gspread()

# --- LOAD MASTER DATA ---
@st.cache_data(ttl=600)
def load_master_data():
    try:
        if not gc:
            return [], [], [], {}
        
        # Mở sheet
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        
        # Đọc worksheet CONFIG
        worksheet = sh.worksheet("CONFIG")
        records = worksheet.get_all_records()
        df_config = pd.DataFrame(records)
        
        # Parse data
        list_nha_cung_cap = df_config['nha_cung_cap'].dropna().unique().tolist()
        list_nha_may = df_config['noi_may'].dropna().unique().tolist()
        
        # Filter errors for 'May' group + 'chung'
        if 'nhom_loi' in df_config.columns:
            target_groups = ['may', 'chung']
            list_loi = sorted(df_config[df_config['nhom_loi'].astype(str).str.lower().isin(target_groups)]['ten_loi'].dropna().unique().tolist())
        else:
            list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist())

        list_vi_tri = df_config['vi_tri_loi'].dropna().unique().tolist()
        dict_muc_do = df_config.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
        
        return list_nha_cung_cap, list_nha_may, list_loi, list_vi_tri, dict_muc_do
        
    except Exception as e:
        st.error(f"Lỗi đọc Config: {e}")
        import traceback
        st.code(traceback.format_exc())
        return [], [], [], {}

LIST_NHA_CUNG_CAP, LIST_NHA_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data()

# --- SESSION STATE ---
if "buffer_errors" not in st.session_state:
    st.session_state.buffer_errors = []
if "header_locked" not in st.session_state:
    st.session_state.header_locked = False

# --- GIAO DIỆN ---
st.title("📱 QC NCR Input")

# === PHẦN 1: HEADER (THÔNG TIN PHIẾU) ===
# Mặc định expander đóng nếu đã khóa, mở nếu chưa khóa
with st.expander("📝 Thông tin Phiếu (Header)", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    # ROW 1
    c1, c2 = st.columns(2)
    with c1:
        # Auto-fill Creator
        current_user_name = st.session_state["user_info"]["name"]
        nguoi_lap = st.text_input("Người lập", value=current_user_name, disabled=True)
        
        # NCR Logic
        dept_prefix = REQUIRED_DEPT.upper().replace("_", "-") # e.g. MAY_I -> MAY-I
        current_month = datetime.now().strftime("%m")
        ncr_suffix = st.text_input("Số đuôi NCR (xx)", help="Chỉ nhập số đuôi", disabled=disable_hd)
        so_phieu = ""
        if ncr_suffix:
            so_phieu = f"{dept_prefix}-{current_month}-{ncr_suffix}"
            st.caption(f"👉 Mã phiếu: **{so_phieu}**")

    with c2:
        # Material Code
        raw_ma_vt = st.text_input("Mã Vật Tư (xxxyyyyy)", disabled=disable_hd)
        ma_vt = raw_ma_vt.upper().strip() if raw_ma_vt else ""
        
        # Contract Logic (Single Input)
        raw_hop_dong = st.text_input("Hợp đồng (xxxx/yyZZZ)", disabled=disable_hd)
        hop_dong = format_contract_code(raw_hop_dong) if raw_hop_dong else ""

    # ROW 2 (Remaining fields)
    c3, c4 = st.columns(2)
    with c3:
         sl_kiem = st.number_input("SL Kiểm", min_value=0, value=0, disabled=disable_hd)
         ten_sp = st.text_input("Tên SP", disabled=disable_hd)
         
    with c4:
         nguon_goc = st.text_input("Nguồn gốc", placeholder="VD: Nhà máy A", disabled=disable_hd)
         sl_lo = st.number_input("SL Lô", min_value=0, value=0, disabled=disable_hd)

# Phân loại
phan_loai = st.selectbox("Phân loại", ["", "Túi TP", "NPL"], disabled=disable_hd)

# Mô tả lỗi
mo_ta_loi = st.text_area("Mô tả lỗi (chi tiết)", placeholder="Nhập mô tả chi tiết về lỗi...", disabled=disable_hd, height=100)

# Image Upload
st.markdown("**📷 Hình ảnh:**")
uploaded_images = st.file_uploader("Chọn ảnh minh họa", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, disabled=disable_hd, key="img_07")

# Lock Logic
    st.write("") # Spacer
    lock = st.checkbox("🔒 Khóa thông tin (Đã nhập xong)", value=st.session_state.header_locked)
    if lock != st.session_state.header_locked:
        st.session_state.header_locked = lock
        st.rerun()

# === PHẦN 2: CHI TIẾT LỖI ===
st.divider()
st.subheader("Chi tiết lỗi")

# Tách logic nhập lỗi mới ra Tabs để tránh giật màn hình
tab_chon, tab_moi = st.tabs(["📋 Chọn lỗi có sẵn", "➕ Nhập lỗi mới"])

final_ten_loi = ""
# Default values
default_muc_do = "Nhẹ"
final_so_luong = 1

# === TAB 1: CHỌN LỖI ===
with tab_chon:
    c1, c2 = st.columns([2, 1])
    with c1:
        selected_loi = st.selectbox("Tên lỗi", ["-- Chọn --"] + LIST_LOI, key="select_loi")
    with c2:
        so_luong_chon = st.number_input("SL", min_value=1, value=1, key="sl_chon")
    
    if selected_loi != "-- Chọn --":
        final_ten_loi = selected_loi
        final_so_luong = so_luong_chon
        # Auto determine default severity from Dict
        default_muc_do = DICT_MUC_DO.get(final_ten_loi, "Nhẹ")
        if default_muc_do not in ["Nhẹ", "Nặng", "Nghiêm trọng"]:
            default_muc_do = "Nhẹ"

# === TAB 2: NHẬP MỚI ===
with tab_moi:
    st.caption("Nhập tên lỗi chưa có trong danh sách:")
    new_loi_name = st.text_input("Tên lỗi mới", placeholder="Ví dụ: Rách nách...", key="new_loi_input")
    sl_moi = st.number_input("SL", min_value=1, value=1, key="sl_moi")
    
    if new_loi_name:
        final_ten_loi = new_loi_name
        final_so_luong = sl_moi
        # Default severity for new error remains "Nhẹ"

# === VỊ TRÍ (Row 2) ===
st.write("")
col_vitri, col_spacer = st.columns([2, 1])
with col_vitri:
    vi_tri = st.selectbox("Vị trí", LIST_VI_TRI if LIST_VI_TRI else ["Chưa có"], key="select_vitri")
    if st.checkbox("Vị trí khác?", key="chk_vitri_khac"):
        vi_tri = st.text_input("Nhập vị trí:", key="input_vitri_khac")

# === MỨC ĐỘ (Row 3 - Theo yêu cầu: Sau Vị trí) ===
# Dùng pills cho dễ chọn trên mobile
final_muc_do = st.pills("Mức độ", ["Nhẹ", "Nặng", "Nghiêm trọng"], default=default_muc_do, selection_mode="single", key="pills_muc_do_final")
if not final_muc_do:
    final_muc_do = default_muc_do

st.write("") # Spacer
        
# NÚT THÊM (Chung)
if st.button("THÊM LỖI ⬇️", use_container_width=True, type="secondary"):
    if not final_ten_loi or final_ten_loi == "-- Chọn --":
        st.error("Vui lòng chọn hoặc nhập tên lỗi!")
    else:
        found = False
        for item in st.session_state.buffer_errors:
            if item['ten_loi'] == final_ten_loi and item['vi_tri'] == vi_tri:
                item['sl_loi'] += final_so_luong
                found = True
                st.toast(f"Cộng dồn: {final_ten_loi} (+{final_so_luong})")
                break
        if not found:
            st.session_state.buffer_errors.append({
                "ten_loi": final_ten_loi,
                "vi_tri": vi_tri,
                "muc_do": final_muc_do,
                "sl_loi": final_so_luong
            })
            st.toast(f"Đã thêm: {final_ten_loi}")
            
        # Reset UI (Optional - Streamlit auto resets on interaction but inputs stay)
        # Để reset input, cần dùng session state callback hoặc key trick, nhưng tạm thời giữ simple.

# REVIEW & SAVE
st.markdown("### 📋 Buffer")

if len(st.session_state.buffer_errors) > 0:
    # Use mobile helper to render and handle deletes
    st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)
     
    # Calculate sum for display (optional, or rely on helper)
    total_qty = sum([e['sl_loi'] for e in st.session_state.buffer_errors])
    st.caption(f"Tổng lỗi: {total_qty}")

    if st.button("💾 LƯU", type="primary", use_container_width=True):
        try:
            with st.spinner("Đang lưu..."):
                hinh_anh_links = ""
                if uploaded_images:
                    hinh_anh_links = upload_images_to_drive(uploaded_images, so_phieu)
                
                sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                ws = sh.worksheet("NCR_DATA")
                
                now = datetime.now()
                rows = []
                for err in st.session_state.buffer_errors:
                    rows.append([
                        now.strftime("%Y-%m-%d %H:%M:%S"),  # 1. ngay_lap
                        so_phieu,                           # 2. so_phieu_ncr
                        hop_dong,                           # 3. hop_dong
                        ma_vt,                              # 4. ma_vat_tu
                        ten_sp,                             # 5. ten_sp
                        phan_loai,                                 # 6. phan_loai
                        nguon_goc,                          # 7. nguon_goc
                        err['ten_loi'],                     # 8. ten_loi
                        err['vi_tri'],                      # 9. vi_tri_loi
                        err['sl_loi'],                      # 10. so_luong_loi
                        sl_kiem,                            # 11. so_luong_kiem
                        err['muc_do'],                      # 12. muc_do
                        mo_ta_loi,                          # 13. mo_ta_loi (NEW)
                        sl_lo,                              # 14. so_luong_lo_hang
                        nguoi_lap,                          # 15. nguoi_lap_phieu
                        nguon_goc,                          # 16. noi_gay_loi
                        # --- NEW APPROVAL COLUMNS ---
                        'cho_truong_ca',                    # 17. trang_thai
                        now.strftime("%Y-%m-%d %H:%M:%S"),  # 18. thoi_gian_cap_nhat
                        phan_loai,                                 # 19. duyet_truong_ca
                        phan_loai,                                 # 20. duyet_truong_bp
                        phan_loai,                                 # 21. y_kien_qc
                        phan_loai,                                 # 22. duyet_qc_manager
                        phan_loai,                                 # 23. duyet_giam_doc
                        phan_loai,                                 # 24. duyet_bgd_tan_phu (NEW)
                        phan_loai,                                 # 25. ly_do_tu_choi
                        hinh_anh_links                      # 26. hinh_anh (NEW)
                    ])
                
                ws.append_rows(rows)
                st.success("✅ Đã lưu!")
                st.session_state.buffer_errors = []
                st.balloons()
                
        except Exception as e:
            st.error(f"Lỗi: {e}")
            import traceback
            st.code(traceback.format_exc())
else:
    st.info("Chưa có lỗi")
