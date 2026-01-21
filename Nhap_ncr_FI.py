import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="QC Mobile NCR", page_icon="📱", layout="centered")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def init_gspread():
    """Khởi tạo gspread client từ secrets"""
    try:
        # Lấy service account credentials từ secrets
        credentials_dict = dict(st.secrets["connections"]["gsheets"]["service_account"])
        
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
        list_nha_may = df_config['noi_may'].dropna().unique().tolist()
        list_loi = sorted(df_config['ten_loi'].dropna().unique().tolist())
        list_vi_tri = df_config['vi_tri_loi'].dropna().unique().tolist()
        dict_muc_do = df_config.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
        
        return list_nha_may, list_loi, list_vi_tri, dict_muc_do
        
    except Exception as e:
        st.error(f"Lỗi đọc Config: {e}")
        import traceback
        st.code(traceback.format_exc())
        return [], [], [], {}

LIST_NHA_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data()

# --- SESSION STATE ---
if "buffer_errors" not in st.session_state:
    st.session_state.buffer_errors = []
if "header_locked" not in st.session_state:
    st.session_state.header_locked = False

# --- GIAO DIỆN ---
st.title("📱 QC NCR Input")

# HEADER
with st.expander("📝 Thông tin Phiếu", expanded=not st.session_state.header_locked):
    lock = st.checkbox("🔒 Khóa Header", value=st.session_state.header_locked)
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
        ten_sp = st.text_input("Tên SP", disabled=disable_hd)
        nha_may = st.selectbox("Nơi may", [""] + LIST_NHA_MAY, disabled=disable_hd)
        sl_lo = st.number_input("SL Lô", min_value=0, value=0, disabled=disable_hd)

# CHI TIẾT
st.divider()
st.subheader("Chi tiết lỗi")

c_loi, c_vitri, c_sl = st.columns([2, 1.5, 1])

with c_loi:
    input_loi = st.selectbox("Tên lỗi", ["-- Chọn --"] + LIST_LOI + ["➕ Lỗi mới..."])
    final_ten_loi, final_muc_do = "", "Nhẹ"
    
    if input_loi == "➕ Lỗi mới...":
        final_ten_loi = st.text_input("Nhập tên lỗi:")
        final_muc_do = st.selectbox("Mức độ", ["Nhẹ", "Nặng", "Nghiêm trọng"])
    elif input_loi != "-- Chọn --":
        final_ten_loi = input_loi
        auto_muc_do = DICT_MUC_DO.get(final_ten_loi, "")
        if auto_muc_do:
            st.info(f"Mức độ: {auto_muc_do}")
            final_muc_do = auto_muc_do
        else:
            final_muc_do = st.selectbox("Mức độ", ["Nhẹ", "Nặng", "Nghiêm trọng"])

with c_vitri:
    vi_tri = st.selectbox("Vị trí", LIST_VI_TRI if LIST_VI_TRI else ["Chưa có"])
    if st.checkbox("Vị trí khác?"):
        vi_tri = st.text_input("Nhập vị trí:")

with c_sl:
    so_luong = st.number_input("SL", min_value=1, value=1)

# THÊM LỖI
if st.button("THÊM LỖI ⬇️", use_container_width=True, type="secondary"):
    if not final_ten_loi or input_loi == "-- Chọn --":
        st.error("Chọn tên lỗi!")
    else:
        found = False
        for item in st.session_state.buffer_errors:
            if item['ten_loi'] == final_ten_loi and item['vi_tri'] == vi_tri:
                item['sl_loi'] += so_luong
                found = True
                st.toast(f"Cộng dồn: {final_ten_loi} (+{so_luong})")
                break
        if not found:
            st.session_state.buffer_errors.append({
                "ten_loi": final_ten_loi,
                "vi_tri": vi_tri,
                "muc_do": final_muc_do,
                "sl_loi": so_luong
            })
            st.toast(f"Đã thêm: {final_ten_loi}")

# REVIEW & SAVE
st.markdown("### 📋 Buffer")

if len(st.session_state.buffer_errors) > 0:
    df_buffer = pd.DataFrame(st.session_state.buffer_errors)
    st.dataframe(df_buffer, use_container_width=True)
    st.caption(f"Tổng: {df_buffer['sl_loi'].sum()}")

    if st.button("💾 LƯU", type="primary", use_container_width=True):
        try:
            with st.spinner("Đang lưu..."):
                sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                ws = sh.worksheet("NCR_DATA")
                
                now = datetime.now()
                rows = []
                for err in st.session_state.buffer_errors:
                    rows.append([
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        now.strftime("%Y-%m-%d"),
                        nguoi_lap, so_phieu, hop_dong, ma_vt, ten_sp, nha_may,
                        err['ten_loi'], err['vi_tri'], err['muc_do'], err['sl_loi'],
                        sl_kiem, sl_lo, nha_may
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
