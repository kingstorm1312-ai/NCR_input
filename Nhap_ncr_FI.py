import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="QC Mobile NCR", page_icon="📱", layout="centered")

# --- KẾT NỐI GOOGLE SHEETS VỚI GSPREAD ---
@st.cache_resource
def get_gspread_client():
    """Tạo gspread client với credentials từ Streamlit secrets"""
    try:
        # Lấy credentials từ secrets
        creds_dict = st.secrets["connections"]["gsheets"]["service_account"]
        
        # Parse JSON nếu cần
        if isinstance(creds_dict, str):
            import json
            creds_dict = json.loads(creds_dict)
        
        # Tạo credentials object
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Tạo gspread client
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Lỗi kết nối Google Sheets: {e}")
        return None

# --- LOAD MASTER DATA (CACHE ĐỂ CHẠY NHANH) ---
@st.cache_data(ttl=600)  # Cache 10 phút
def load_master_data():
    try:
        # Lấy client
        client = get_gspread_client()
        if not client:
            return [], [], [], {}
        
        # Mở sheet bằng ID
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Đọc worksheet CONFIG
        worksheet = spreadsheet.worksheet("CONFIG")
        data = worksheet.get_all_records()
        
        # Convert sang DataFrame
        df_config = pd.DataFrame(data)
        
        # 1. Danh sách Nhà gia công
        list_nha_may = df_config['noi_may'].dropna().unique().tolist()
        
        # 2. Danh sách Lỗi (Sắp xếp A-Z)
        list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist())
        
        # 3. Danh sách Vị trí
        list_vi_tri = df_config['vi_tri_loi'].dropna().unique().tolist()
        
        # 4. Dictionary Mức độ
        dict_muc_do = df_config.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
        
        return list_nha_may, list_loi, list_vi_tri, dict_muc_do
        
    except Exception as e:
        st.error(f"Lỗi đọc Config: {e}")
        import traceback
        st.error(traceback.format_exc())
        return [], [], [], {}

# Load dữ liệu
LIST_NHA_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data()

# --- KHỞI TẠO SESSION STATE ---
if "buffer_errors" not in st.session_state:
    st.session_state.buffer_errors = []
if "header_locked" not in st.session_state:
    st.session_state.header_locked = False

# --- GIAO DIỆN CHÍNH ---
st.title("📱 QC NCR Input")

# === PHẦN 1: HEADER ===
with st.expander("📝 Thông tin Phiếu (Header)", expanded=not st.session_state.header_locked):
    lock = st.checkbox("🔒 Khóa thông tin (Để nhập lỗi)", value=st.session_state.header_locked)
    st.session_state.header_locked = lock
    
    disable_hd = st.session_state.header_locked
    
    col1, col2 = st.columns(2)
    with col1:
        so_phieu = st.text_input("Số phiếu NCR", disabled=disable_hd)
        ma_vt = st.text_input("Mã Vật Tư", disabled=disable_hd)
        sl_kiem = st.number_input("SL Kiểm", min_value=0, value=0, disabled=disable_hd)
        nguoi_lap = st.text_input("Người lập", value="QC", disabled=disable_hd)
    with col2:
        hop_dong = st.text_input("Hợp đồng", disabled=disable_hd)
        ten_sp = st.text_input("Tên Sản Phẩm", disabled=disable_hd)
        nha_may = st.selectbox("Nơi may / Nhà GC", [""] + LIST_NHA_MAY, disabled=disable_hd)
        sl_lo = st.number_input("SL Lô hàng", min_value=0, value=0, disabled=disable_hd)

# === PHẦN 2: CHI TIẾT LỖI ===
st.divider()
st.subheader("Chi tiết lỗi")

c_loi, c_vitri, c_sl = st.columns([2, 1.5, 1])

with c_loi:
    input_loi = st.selectbox("Tên lỗi", ["-- Chọn --"] + LIST_LOI + ["➕ Lỗi mới..."])
    
    final_ten_loi = ""
    final_muc_do = "Nhẹ"
    
    if input_loi == "➕ Lỗi mới...":
        final_ten_loi = st.text_input("Nhập tên lỗi mới:")
        final_muc_do = st.selectbox("Mức độ", ["Nhẹ", "Nặng", "Nghiêm trọng"])
    elif input_loi != "-- Chọn --":
        final_ten_loi = input_loi
        auto_muc_do = DICT_MUC_DO.get(final_ten_loi, "")
        if auto_muc_do:
            st.info(f"Mức độ: {auto_muc_do}")
            final_muc_do = auto_muc_do
        else:
            final_muc_do = st.selectbox("Chọn Mức độ", ["Nhẹ", "Nặng", "Nghiêm trọng"])

with c_vitri:
    vi_tri = st.selectbox("Vị trí", LIST_VI_TRI if LIST_VI_TRI else ["Chưa có dữ liệu"])
    if st.checkbox("Vị trí khác?"):
        vi_tri = st.text_input("Nhập vị trí:")

with c_sl:
    so_luong = st.number_input("SL Lỗi", min_value=1, value=1)

# NÚT THÊM
if st.button("THÊM LỖI ⬇️", use_container_width=True, type="secondary"):
    if not final_ten_loi or input_loi == "-- Chọn --":
        st.error("Vui lòng chọn tên lỗi!")
    else:
        # LOGIC CỘNG DỒN
        found = False
        for item in st.session_state.buffer_errors:
            if item['ten_loi'] == final_ten_loi and item['vi_tri'] == vi_tri:
                item['sl_loi'] += so_luong
                found = True
                st.toast(f"Đã cộng dồn: {final_ten_loi} (+{so_luong})")
                break
        
        if not found:
            st.session_state.buffer_errors.append({
                "ten_loi": final_ten_loi,
                "vi_tri": vi_tri,
                "muc_do": final_muc_do,
                "sl_loi": so_luong
            })
            st.toast(f"Đã thêm mới: {final_ten_loi}")

# === PHẦN 3: REVIEW & SAVE ===
st.markdown("### 📋 Danh sách chờ lưu")

if len(st.session_state.buffer_errors) > 0:
    df_buffer = pd.DataFrame(st.session_state.buffer_errors)
    st.dataframe(df_buffer, use_container_width=True)
    
    total_errors = df_buffer['sl_loi'].sum()
    st.caption(f"Tổng số lỗi: {total_errors}")

    # NÚT LƯU
    if st.button("💾 LƯU DỮ LIỆU VÀO SHEET", type="primary", use_container_width=True):
        try:
            with st.spinner("Đang lưu..."):
                # Lấy client
                client = get_gspread_client()
                spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
                spreadsheet = client.open_by_key(spreadsheet_id)
                
                # Mở worksheet NCR_DATA
                worksheet = spreadsheet.worksheet("NCR_DATA")
                
                # Tạo rows để thêm
                current_time = datetime.now()
                rows_to_add = []
                
                for err in st.session_state.buffer_errors:
                    row = [
                        current_time.strftime("%Y-%m-%d %H:%M:%S"),  # timestamp
                        current_time.strftime("%Y-%m-%d"),           # ngay_lap
                        nguoi_lap,                                    # nguoi_lap_phieu
                        so_phieu,                                     # so_phieu_ncr
                        hop_dong,                                     # hop_dong
                        ma_vt,                                        # ma_vat_tu
                        ten_sp,                                       # ten_sp
                        nha_may,                                      # noi_may
                        err['ten_loi'],                              # ten_loi
                        err['vi_tri'],                               # vi_tri_loi
                        err['muc_do'],                               # muc_do
                        err['sl_loi'],                               # so_luong_loi
                        sl_kiem,                                      # so_luong_kiem
                        sl_lo,                                        # so_luong_lo_hang
                        nha_may                                       # noi_gay_loi
                    ]
                    rows_to_add.append(row)
                
                # Append rows vào sheet
                worksheet.append_rows(rows_to_add)
                
                st.success("✅ Đã lưu thành công!")
                st.session_state.buffer_errors = []
                st.balloons()
                
        except Exception as e:
            st.error(f"Lỗi khi lưu: {e}")
            import traceback
            st.error(traceback.format_exc())

else:
    st.info("Chưa có lỗi nào được nhập.")
