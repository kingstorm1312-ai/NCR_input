import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
import sys
import os

# Utils Import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import format_contract_code, render_input_buffer_mobile, upload_images_to_cloud

# --- CONFIGURATION ---
REQUIRED_DEPT = 'fi'
PAGE_TITLE = "QC Input - FI"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🔍", layout="centered")

# --- SECURITY ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập!")
    st.stop()

user_info = st.session_state.user_info
if user_info.get("role") != 'admin' and user_info.get("department") != REQUIRED_DEPT:
    st.error("⛔ Không có quyền truy cập.")
    st.stop()

# --- GSHEETS ---
@st.cache_resource
def init_gspread():
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        if isinstance(creds_str, str):
            creds_dict = json.loads(creds_str, strict=False)
        else:
            creds_dict = creds_str
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Lỗi Gsheets: {e}")
        return None

gc = init_gspread()

# --- LOAD CONFIG ---
@st.cache_data(ttl=600)
def load_master_data():
    try:
        if not gc: return [], [], {}, []
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        df = pd.DataFrame(sh.worksheet("CONFIG").get_all_records())
        
        # Filter Errors
        if 'nhom_loi' in df.columns:
            target_groups = ['fi', 'chung']
            list_loi = sorted(df[df['nhom_loi'].astype(str).str.lower().isin(target_groups)]['ten_loi'].dropna().unique().tolist())
        else:
            list_loi = sorted(df['ten_loi'].dropna().unique().tolist())

        list_vi_tri = df['vi_tri_loi'].dropna().unique().tolist() if 'vi_tri_loi' in df.columns else []
        dict_muc_do = df.drop_duplicates(subset=['ten_loi']).set_index('ten_loi')['muc_do'].to_dict()
        
        return list_loi, list_vi_tri, dict_muc_do
    except Exception:
        return [], [], {}

LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data()

# --- STATE ---
if "buffer_errors" not in st.session_state: st.session_state.buffer_errors = []
if "header_locked" not in st.session_state: st.session_state.header_locked = False

# --- UI ---
st.title("🔍 QC Input - FI")

with st.expander("📝 Thông tin Phiếu", expanded=not st.session_state.header_locked):
    disable_hd = st.session_state.header_locked
    
    c1, c2 = st.columns(2)
    with c1:
        nguoi_lap = st.text_input("Người lập", value=user_info["name"], disabled=True)
        # Prefix FI
        prefix = "FI"
        current_month = datetime.now().strftime("%m")
        suffix = st.text_input("Số đuôi NCR (xx)", disabled=disable_hd)
        so_phieu = f"{prefix}-{current_month}-{suffix}" if suffix else ""
        if so_phieu: st.caption(f"Code: **{so_phieu}**")

    with c2:
        ma_vt = st.text_input("Mã VT", disabled=disable_hd).upper().strip()
        hop_dong = format_contract_code(st.text_input("Hợp đồng", disabled=disable_hd))

    c3, c4 = st.columns(2)
    with c3:
        sl_kiem = st.number_input("SL Kiểm", min_value=0, disabled=disable_hd)
        ten_sp = st.text_input("Tên SP", disabled=disable_hd)
    with c4:
        nguon_goc = st.text_input("Nguồn gốc (NCC)", disabled=disable_hd)
        sl_lo = st.number_input("SL Lô (so_lo)", min_value=0, disabled=disable_hd)

    # Note: User asked to pass "" for phan_loai, so no UI needed for it.
    
    quy_cach = st.text_area("Mô tả lỗi / Quy cách", height=100, disabled=disable_hd)
    
    st.markdown("**📷 Hình ảnh:**")
    uploaded_imgs = st.file_uploader("Chọn ảnh", type=['png','jpg','jpeg'], accept_multiple_files=True, disabled=disable_hd)

    lock = st.checkbox("🔒 Khóa thông tin", value=st.session_state.header_locked)
    if lock != st.session_state.header_locked:
        st.session_state.header_locked = lock
        st.rerun()

st.divider()
st.subheader("Chi tiết lỗi")

tab1, tab2 = st.tabs(["Chọn Lỗi", "Nhập Mới"])
with tab1:
    sel_loi = st.selectbox("Tên lỗi", ["--"] + LIST_LOI)
    sl_sel = st.number_input("SL", min_value=1, key="s1")
    if sel_loi != "--":
        final_loi = sel_loi
        final_sl = sl_sel
        final_md = DICT_MUC_DO.get(final_loi, "Nhẹ")
    else:
        final_loi = ""
        final_sl = 1
        final_md = "Nhẹ"

with tab2:
    new_loi = st.text_input("Lỗi mới")
    sl_new = st.number_input("SL", min_value=1, key="s2")
    if new_loi:
        final_loi = new_loi
        final_sl = sl_new
        final_md = "Nhẹ"

col_vt, _ = st.columns([2,1])
with col_vt:
    vi_tri = st.selectbox("Vị trí", LIST_VI_TRI if LIST_VI_TRI else [""])
    if st.checkbox("Vị trí khác?"):
        vi_tri = st.text_input("Nhập vị trí")

valid_md = ["Nhẹ", "Nặng", "Nghiêm trọng"]
if final_md not in valid_md:
    final_md = "Nhẹ"
final_md = st.pills("Mức độ", valid_md, default=final_md, selection_mode="single") or final_md

if st.button("THÊM LỖI ⬇️", type="secondary", use_container_width=True):
    if not final_loi:
        st.error("Chưa chọn lỗi!")
    else:
        st.session_state.buffer_errors.append({
            "ten_loi": final_loi, "sl_loi": final_sl, "vi_tri": vi_tri, "muc_do": final_md
        })
        st.toast(f"Đã thêm: {final_loi}")

st.markdown("### 📋 Buffer")
if st.session_state.buffer_errors:
    st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)
    
    if st.button("💾 LƯU PHIẾU", type="primary", use_container_width=True):
        try:
            with st.spinner("Đang lưu lên Cloud & Sheets..."):
                # 1. Upload Cloudinary
                img_links = upload_images_to_cloud(uploaded_imgs, so_phieu)
                
                # 2. Save to Sheet
                sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                ws = sh.worksheet("NCR_DATA")
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Read headers from Sheet (row 1)
                headers = ws.row_values(1)
                
                rows = []
                for err in st.session_state.buffer_errors:
                    # Create data dictionary
                    data = {
                        'ngày lập': now,
                        'số phiếu ncr': so_phieu,
                        'hợp đồng': hop_dong,
                        'mã vật tư': ma_vt,
                        'tên sp': ten_sp,
                        'phân loại': "",  # Empty for FI
                        'nguồn gốc': nguon_goc,
                        'tên lỗi': err['ten_loi'],
                        'vị trí lỗi': err['vi_tri'],
                        'số lượng lỗi': err['sl_loi'],
                        'số lượng kiểm': sl_kiem,
                        'mức độ': err['muc_do'],
                        'mô tả lỗi': quy_cach,
                        'số lượng lô': sl_lo,
                        'người lập phiếu': nguoi_lap,
                        'nơi gây lỗi': nguon_goc,
                        'trạng thái': 'cho_truong_ca',
                        'thời gian cập nhật': now,
                        'duyệt trưởng ca': '',
                        'duyệt trưởng bp': '',
                        'ý kiến QC': '',
                        'duyệt QC manager': '',
                        'duyet giam doc': '',
                        'duyet bgd tan phu': '',
                        'ly do từ chối': '',
                        'hình ảnh': img_links
                    }
                    
                    # Map to row based on headers
                    row = [data.get(h, '') for h in headers]
                    rows.append(row)
                
                ws.append_rows(rows)
                st.success("✅ Đã lưu thành công!")
                st.balloons()
                st.session_state.buffer_errors = []
                
        except Exception as e:
            st.error(f"Lỗi: {e}")
