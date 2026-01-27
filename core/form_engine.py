import streamlit as st
from core.profile import DeptProfile
from core.auth import require_dept_access
from core.master_data import load_config_sheet
from core.gsheets import get_client, smart_append_batch, open_worksheet
from core.state import init_session_state
from utils.ncr_helpers import (
    get_now_vn, get_now_vn_str,
    format_contract_code, 
    render_input_buffer_mobile, 
    upload_images_to_cloud,
    LIST_DON_VI_TINH,
    get_initial_status
)
from utils.aql_manager import get_aql_standard, evaluate_lot_quality
from utils.config import NCR_DEPARTMENT_PREFIXES

# --- PHÂN LOẠI ĐẶC THÙ (Dynamic Prefixes) ---
DYNAMIC_PREFIX_BY_CODE = {
    "trang_cat": {
        "Tráng": NCR_DEPARTMENT_PREFIXES.get("TRANG", "X2-TR"),
        "Cắt": NCR_DEPARTMENT_PREFIXES.get("CAT", "X2-CA")
    },
    "in_xuong_d": {
        "In": NCR_DEPARTMENT_PREFIXES.get("IN", "XG-IN"),
        "Siêu Âm": NCR_DEPARTMENT_PREFIXES.get("SIEU_AM", "XG-SA")
    }
}

def resolve_prefix(profile: DeptProfile, phan_loai_value: str) -> str:
    """
    Xác định prefix dựa trên profile và giá trị phân loại (nếu có).
    """
    if profile.code in DYNAMIC_PREFIX_BY_CODE:
        mapping = DYNAMIC_PREFIX_BY_CODE[profile.code]
        if phan_loai_value in mapping:
            return mapping[phan_loai_value]
    return profile.prefix

from core.auth import require_dept_access, get_user_info

def run_inspection_page(profile: DeptProfile):
    """
    Engine chạy trang inspection/kiểm tra NCR dựa trên DeptProfile.
    Hỗ trợ cả các bộ phận có AQL (FI, May) và không có AQL (DV NPL).
    """
    # Page config (MUST BE FIRST)
    st.set_page_config(page_title=f"QC Input - {profile.name}", page_icon=profile.icon, layout="centered")

    # Require dept access (already calls require_login via get_user_info inside)
    require_dept_access(profile.code)
    
    user_info = get_user_info()
    
    # Mobile navigation helper
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
    
    # Load master data
    LIST_NOI_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO, _ = load_config_sheet()
    
    # Session state init
    if "buffer_errors" not in st.session_state:
        st.session_state.buffer_errors = []
    if "header_locked" not in st.session_state:
        st.session_state.header_locked = False
    if "custom_sample_size" not in st.session_state:
        st.session_state.custom_sample_size = False
    
    # Title
    st.title(f"{profile.icon} QC Input - {profile.name}")
    
    # ==========================================
    # PHẦN 1: THIẾT LẬP KIỂM TRA (TOP SECTION)
    # ==========================================
    st.subheader("1️⃣ Thiết lập kiểm tra")
    
    # Row 1: SL Lô & SL Mẫu (Sử dụng AQL nếu có)
    c_sl1, c_sl2 = st.columns([1, 1])
    with c_sl1:
        sl_lo = st.number_input("📦 SL Lô Hàng", min_value=0, disabled=st.session_state.header_locked)
    
    sl_kiem = 0
    aql_info = None
    if profile.has_aql:
        # Tính toán AQL tự động
        aql_info = get_aql_standard(sl_lo)
        calc_sample_size = 0
        if aql_info:
            calc_sample_size = aql_info['sample_size']
        
        with c_sl2:
            # Logic Toggle sửa SL Mẫu
            col_inp, col_tog = st.columns([0.8, 0.2])
            with col_tog:
                st.write("")
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
    else:
        # Nếu không dùng AQL, cho phép nhập SL Kiểm tự do
        with c_sl2:
            sl_kiem = st.number_input("SL Kiểm", min_value=0, disabled=st.session_state.header_locked)

    # Row 2: Thông tin định danh
    with st.expander("📝 Thông tin chi tiết (SP, HĐ, Nguồn gốc...)", expanded=not st.session_state.header_locked):
        disable_hd = st.session_state.header_locked
        
        # 3 CỘT INPUT MỚI (CHUNG)
        col_new1, col_new2, col_new3 = st.columns(3)
        with col_new1:
            so_po = st.text_input("Số PO", placeholder="VD: 4500123456", disabled=disable_hd)
        with col_new2:
            don_vi_kiem = st.text_input("Đơn vị kiểm", value="", placeholder="Nhập đơn vị kiểm...", disabled=disable_hd)
        with col_new3:
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
                parts = hop_dong.split('-')
                potential_cust = parts[-1] if not parts[-1].isdigit() else (parts[-2] if len(parts) > 1 else "")
                khach_hang = ''.join(filter(str.isalpha, potential_cust))
                if not khach_hang and len(parts) >= 2:
                     khach_hang = ''.join(filter(str.isalpha, parts[-2]))
                
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
    
        # Nguồn gốc (Sử dụng LIST_NOI_MAY chuẩn)
        nguon_goc_list = st.multiselect("Nguồn gốc (Chuyền/Tổ/NCC)", LIST_NOI_MAY, disabled=disable_hd)
        nguon_goc = ", ".join(nguon_goc_list)

        # Phan loai (nếu profile yêu cầu)
        phan_loai = ""
        if profile.phan_loai_options:
            if profile.code in ["trang_cat", "in_xuong_d"]:
                label = "Khâu:" if profile.code == "in_xuong_d" else "Phân loại:"
                phan_loai = st.radio(label, profile.phan_loai_options, horizontal=True, key="phan_loai_radio", disabled=disable_hd)
            else:
                phan_loai = st.selectbox("Phân loại", profile.phan_loai_options, disabled=disable_hd)
    
        # Lock Toggle
        lock = st.checkbox("🔒 Khóa thông tin chung", value=st.session_state.header_locked)
        if lock != st.session_state.header_locked:
            st.session_state.header_locked = lock
            st.rerun()
    
    # Prefix calculation
    dept_prefix = resolve_prefix(profile, phan_loai)
    
    # ==========================================
    # PHẦN 2: NHẬP KẾT QUẢ (BODY SECTION)
    # ==========================================
    st.markdown("---")
    st.subheader("2️⃣ Kết quả kiểm tra")
    
    # Tabbed Interface or Single List
    show_tabs = profile.has_measurements or profile.has_checklist
    
    # Initialize measurement/checklist vars so they are always in scope for save record
    spec_size = tol_size = meas_size = ""
    spec_weight = tol_weight = meas_weight = ""
    check_barcode = check_weight_box = check_print = check_color = "N/A"
    check_other = ""
    
    if show_tabs:
        tab_measure, tab_defects = st.tabs(["📏 Đo đạc & Checklist", "🐞 Chi tiết Lỗi"])
        
        with tab_measure:
            if profile.has_measurements:
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
            
            if profile.has_checklist:
                st.markdown("**3. Checklist**")
                c_ch1, c_ch2 = st.columns(2)
                check_barcode = c_ch1.selectbox("Mã vạch", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
                check_weight_box = c_ch1.selectbox("Cân thùng", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
                check_print = c_ch2.selectbox("In ấn", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
                check_color = c_ch2.selectbox("Màu sắc", ["N/A", "Đạt", "Không đạt"], disabled=st.session_state.header_locked)
                check_other = st.text_area("Ghi chú khác", height=68, disabled=st.session_state.header_locked)
    else:
        # Nếu không có tabs, chỉ có error list
        tab_defects = st.container()
    
    # --- Đóng gói logic nhập lỗi ---
    with tab_defects:
        if not show_tabs: st.markdown("##### 🐞 Chi tiết Lỗi")
        
        # Toggle Input Mode
        mode_input = st.radio("Chế độ nhập:", ["Chọn từ danh sách", "Nhập mới"], horizontal=True, key="radio_mode")
    
        c_def1, c_def2 = st.columns([2, 1])
    
        if mode_input == "Chọn từ danh sách":
            c_def1.selectbox("Chọn Tên lỗi", ["-- Chọn --"] + LIST_LOI, key="inp_ten_loi")
        else:
            c_def1.text_input("Nhập tên lỗi mới", key="inp_ten_loi_moi")
    
        sl_loi_input = c_def2.number_input("SL Lỗi", min_value=1.0, step=0.1, format="%.1f", key="inp_sl_loi")
    
        c_extra1, c_extra2 = st.columns(2)
        final_md_options = ["Nhẹ", "Nặng", "Nghiêm trọng"]
        final_md = c_extra1.pills("Mức độ", final_md_options, default="Nhẹ", key="inp_muc_do")
    
        vi_tri_sel = c_extra2.selectbox("Vị trí", [""] + LIST_VI_TRI, key="inp_vi_tri_sel")
        vi_tri = vi_tri_sel if vi_tri_sel else st.session_state.get("inp_vi_tri_txt", "")
    
        if not vi_tri_sel: 
            vi_tri_txt = c_extra2.text_input("Vị trí khác", placeholder="Nhập vị trí...", key="inp_vi_tri_txt")
            vi_tri = vi_tri_txt
    
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
            s_pos_sel = st.session_state.get("inp_vi_tri_sel", "")
            s_pos_txt = st.session_state.get("inp_vi_tri_txt", "").strip()
            final_pos = s_pos_sel if s_pos_sel else s_pos_txt
            s_sev = st.session_state.get("inp_muc_do", "Nhẹ")
            
            st.session_state.buffer_errors.append({
                "ten_loi": final_name,
                "vi_tri": final_pos,
                "muc_do": s_sev,
                "sl_loi": s_qty
            })
            
            st.session_state["success_msg"] = f"Đã thêm: {final_name}"
            st.session_state["add_err_msg"] = ""
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
    
        if st.session_state.buffer_errors:
            st.markdown("##### Danh sách đã nhập:")
            st.session_state.buffer_errors = render_input_buffer_mobile(st.session_state.buffer_errors)
    
    # ==========================================
    # PHẦN 3: KẾT LUẬN & XỬ LÝ (ACTION SECTION)
    # ==========================================
    st.markdown("---")
    st.subheader("3️⃣ Kết luận & Xử lý")
    
    final_ncr_num = ""
    mo_ta_loi = ""
    uploaded_images = []
    inspection_result = ""
    
    if profile.has_aql:
        # Tính toán kết quả AQL
        total_major = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] in ['Nặng', 'Nghiêm trọng']])
        total_minor = sum([e['sl_loi'] for e in st.session_state.buffer_errors if e['muc_do'] == 'Nhẹ'])
        inspection_result, aql_details = evaluate_lot_quality(sl_lo, total_major, total_minor)
        
        if inspection_result == 'Pass':
            st.success("✅ **KẾT QUẢ: ĐẠT (PASS)** - Đủ điều kiện nhập kho!")
            if not st.session_state.buffer_errors: st.caption("ℹ️ Không phát hiện lỗi nào.")
            save_label = "💾 LƯU BIÊN BẢN KIỂM TRA (PASS)"
            save_btn_type = "primary"
        else:
            st.error("❌ **KẾT QUẢ: KHÔNG ĐẠT (FAIL)** - Cần lập phiếu NCR!")
            limit_major = aql_details.get('standard', {}).get('ac_major', 0)
            limit_minor = aql_details.get('standard', {}).get('ac_minor', 0)
            c_stat1, c_stat2 = st.columns(2)
            c_stat1.metric("Lỗi Nặng (Major)", f"{total_major}", delta=f"Giới hạn: {limit_major}", delta_color="inverse")
            c_stat2.metric("Lỗi Nhẹ (Minor)", f"{total_minor}", delta=f"Giới hạn: {limit_minor}", delta_color="inverse")
            st.markdown("#### 📝 Thông tin NCR bổ sung")
            save_label = "🚨 LƯU & TẠO PHIẾU NCR"
            save_btn_type = "primary"
    else:
        # Bộ phận không dùng AQL (như DV NPL) - Luôn yêu cầu nhập mã phiếu
        st.info("ℹ️ Nhập thông tin phiếu NCR để lưu danh sách lỗi.")
        save_label = "💾 LƯU PHIẾU NCR"
        save_btn_type = "primary"
    
    # Input chung cho các trường hợp cần NCR hoặc lưu lỗi
    if (not profile.has_aql) or (profile.has_aql and inspection_result == 'Fail'):
        curr_month = get_now_vn().strftime("%m")
        c_ncr1, c_ncr2 = st.columns([1, 2])
        ncr_suffix = c_ncr1.text_input("Số đuôi NCR (xx)", help="Nhập 2 số cuối của phiếu", max_chars=3)
        if ncr_suffix:
            final_ncr_num = f"{dept_prefix}-{curr_month}-{ncr_suffix}"
            c_ncr2.markdown(f"👉 Mã phiếu: **{final_ncr_num}**")
        else:
            c_ncr2.warning("⬅️ Vui lòng nhập số đuôi phiếu NCR")
            
        mo_ta_loi = st.text_area("Mô tả lỗi chi tiết / Nguyên nhân", height=80)
        uploaded_images = st.file_uploader("Hình ảnh bằng chứng", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
    
    # --- NÚT LƯU CUỐI CÙNG ---
    if st.button(save_label, type=save_btn_type, use_container_width=True):
        if (not profile.has_aql or inspection_result == 'Fail') and not final_ncr_num:
            st.error("⚠️ Vui lòng nhập SỐ ĐUÔI NCR trước khi lưu!")
            st.stop()
        
        if not st.session_state.buffer_errors and not profile.has_aql:
            st.error("⚠️ Danh sách lỗi trống!")
            st.stop()
    
        try:
            with st.spinner("Đang lưu dữ liệu hệ thống..."):
                if uploaded_images:
                    img_links = upload_images_to_cloud(uploaded_images, final_ncr_num if final_ncr_num else "PASS_REC")
                else:
                    img_links = ""
                    
                gc = get_client()
                if not gc:
                    st.error("Lỗi kết nối Google Sheets")
                    st.stop()
                
                ws = open_worksheet(profile.sheet_spreadsheet_id, profile.sheet_worksheet_name)
                if not ws: st.stop()
    
                now = get_now_vn_str()
                records_to_save = st.session_state.buffer_errors
                if profile.has_aql and inspection_result == 'Pass' and not records_to_save:
                    records_to_save = [{"ten_loi": "Không có lỗi", "vi_tri": "", "muc_do": "", "sl_loi": 0}]
                    
                current_status = "Hoàn thành" if inspection_result == 'Pass' else get_initial_status(profile.code)
                
                batch_data = []
                for err in records_to_save:
                    row_data = {
                        'ngay_lap': now,
                        'so_phieu_ncr': final_ncr_num,
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
                        'nguoi_lap_phieu': user_info.get("name"),
                        'noi_gay_loi': nguon_goc,
                        'trang_thai': current_status,
                        'thoi_gian_cap_nhat': now,
                        'hinh_anh': img_links,
                        'don_vi_tinh': don_vi_tinh,
                        'ket_qua_kiem_tra': inspection_result,
                        'spec_size': spec_size, 'tol_size': tol_size, 'meas_size': meas_size,
                        'spec_weight': spec_weight, 'tol_weight': tol_weight, 'meas_weight': meas_weight,
                        'check_barcode': check_barcode, 'check_weight_box': check_weight_box,
                        'check_print': check_print, 'check_color': check_color, 'check_other': check_other,
                        'so_po': so_po, 'khach_hang': khach_hang, 'don_vi_kiem': don_vi_kiem
                    }
                    batch_data.append(row_data)
                    
                success_count = smart_append_batch(ws, batch_data)
                if success_count > 0:
                    st.balloons()
                    st.success(f"✅ Đã lưu thành công {success_count} dòng! ({inspection_result})")
                    st.session_state.buffer_errors = []
                    st.session_state.header_locked = False
                else:
                    st.error("Lỗi khi lưu dữ liệu vào Sheet.")
        except Exception as e:
            st.error(f"System Error: {e}")
