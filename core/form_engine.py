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
    get_initial_status,
    generate_next_pass_id,
    generate_next_ncr_id,
    is_ncr_id_exists
)
from utils.aql_manager import get_aql_standard, evaluate_lot_quality
from utils.config import NCR_DEPARTMENT_PREFIXES
from core.voice_input_service import process_audio_defect
from utils.measurement_utils import generate_random_measurement

def auto_gen_measurement_callback(key, spec, tol):
    """Callback xử lý sự kiện bấm nút 🎲"""
    new_val = generate_random_measurement(spec, tol)
    if new_val:
        current_val = st.session_state.get(key, "")
        if current_val:
             st.session_state[key] = f"{current_val} - {new_val}"
        else:
             st.session_state[key] = new_val

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

    # Require dept access (already handles login and sidebar)
    user_info = require_dept_access(profile.code)

    
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
                is_custom = st.checkbox("🔓", value=st.session_state.custom_sample_size, help="Mở khóa để sửa SL Mẫu & Giới hạn", key="chk_custom_sample")
                st.session_state.custom_sample_size = is_custom
            
            with col_inp:
                if st.session_state.custom_sample_size:
                     sl_kiem = st.number_input("SL Mẫu (Tùy chỉnh)", min_value=0, value=calc_sample_size, disabled=st.session_state.header_locked)
                     
                     # --- CUSTOM LIMITS INPUTS ---
                     c_lim1, c_lim2 = st.columns(2)
                     # Determine default values for limits (from AQL or 0)
                     def_ac_major = aql_info['ac_major'] if aql_info else 0
                     def_ac_minor = aql_info['ac_minor'] if aql_info else 0
                     
                     custom_major = c_lim1.number_input("Max Lỗi Nặng", value=def_ac_major, min_value=0, key="cust_ac_maj")
                     custom_minor = c_lim2.number_input("Max Lỗi Nhẹ", value=def_ac_minor, min_value=0, key="cust_ac_min")
                     
                else:
                     sl_kiem = st.number_input("SL Mẫu (AQL)", value=calc_sample_size, disabled=True, help="Tự động tính theo AQL Level II")
                     custom_major = None
                     custom_minor = None
        
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
                meas_size_val = c_sz3.text_area("Thực tế (Size)", placeholder="VD: 20, 21...", height=68, disabled=st.session_state.header_locked, key="txt_meas_size_input")
                # Auto-Generate Button for Size
                if not st.session_state.header_locked:
                    c_sz3.button("🎲", key="btn_gen_size", help="Tự động tạo số liệu đo đạc (Size)", 
                                 on_click=auto_gen_measurement_callback, 
                                 args=("txt_meas_size_input", spec_size, tol_size))

                # Sync variable for save logic
                meas_size = st.session_state.get("txt_meas_size_input", "")

                st.markdown("**2. Trọng lượng (Weight)**")
                c_w1, c_w2, c_w3 = st.columns(3)
                spec_weight = c_w1.text_input("Tiêu chuẩn (Weight)", placeholder="VD: 500g", disabled=st.session_state.header_locked)
                tol_weight = c_w2.text_input("Dung sai (Weight)", placeholder="VD: +/- 5g", disabled=st.session_state.header_locked)
                
                # Manual or Auto Input for Weight
                meas_weight_val = c_w3.text_area("Thực tế (Weight)", placeholder="VD: 501, 499...", height=68, disabled=st.session_state.header_locked, key="txt_meas_weight_input")
                 # Auto-Generate Button for Weight
                if not st.session_state.header_locked:
                    c_w3.button("🎲", key="btn_gen_weight", help="Tự động tạo số liệu đo đạc (Weight)",
                                on_click=auto_gen_measurement_callback,
                                args=("txt_meas_weight_input", spec_weight, tol_weight))
                
                meas_weight = st.session_state.get("txt_meas_weight_input", "")
            
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
        
        # --- DIALOG DEFINITION (Mobile Optimized) ---
        @st.dialog("📝 Thêm lỗi mới")
        def open_add_defect_dialog():
            # Use st.fragment if available to prevent full rerun closure
            try:
                from streamlit import fragment
            except ImportError:
                # Fallback: Just define decorator as pass-through if basic (won't solve close, but prevents crash)
                # But user likely deals with closure issue, so assume fragment exists or we rely on session state fallback? 
                # Let's assume Streamlit >= 1.37 as per project context (modern).
                fragment = lambda func: func

            @fragment
            def inner_defect_form():
                # SHOW TOAST INSIDE DIALOG (Because rerun only refreshes dialog)
                if st.session_state.get("success_msg"):
                    st.toast(st.session_state["success_msg"], icon="✅")
                    st.session_state["success_msg"] = "" # Clear after showing

                # 1. Tên lỗi
                mode_input = st.radio("Nguồn tên lỗi:", ["Chọn danh sách", "Nhập tay"], horizontal=True, label_visibility="collapsed", key="rd_mode_input_source")
                col_name = st.container()
                if mode_input == "Chọn danh sách":
                    s_loi = col_name.selectbox("Tên lỗi", [""] + LIST_LOI, key="dlg_ten_loi", help="Chọn tên lỗi từ danh sách")
                    final_name = s_loi
                else:
                    s_loi_new = col_name.text_input("Nhập tên lỗi", key="dlg_ten_loi_new", placeholder="Nhập tên lỗi mới...")
                    final_name = s_loi_new

                # 2. Vị trí
                col_pos = st.container()
                c_p1, c_p2 = col_pos.columns([1, 1])
                vi_tri_sel = c_p1.selectbox("Vị trí", [""] + LIST_VI_TRI, key="dlg_vi_tri_sel")
                if not vi_tri_sel:
                    vi_tri_txt = c_p2.text_input("Vị trí khác", placeholder="Ghi cụ thể...", key="dlg_vi_tri_txt")
                    final_pos = vi_tri_txt
                else:
                    c_p2.write("") # Spacer
                    final_pos = vi_tri_sel

                # 3. Số lượng (Strict Type Handling)
                is_continuous = don_vi_tinh and str(don_vi_tinh).lower() in ['kg', 'mét', 'm', 'met']
                
                c_qty, c_sev = st.columns([1, 1])
                with c_qty:
                    if is_continuous:
                        # Float path
                        s_qty = st.number_input("SL Lỗi", min_value=0.1, step=0.1, value=1.0, format="%.1f", key="dlg_qty_float")
                    else:
                        # Integer path (Fix warning)
                        s_qty = st.number_input("SL Lỗi", min_value=1, step=1, value=1, format="%d", key="dlg_qty_int")
                
                with c_sev:
                    final_md_options = ["Nhẹ", "Nặng", "Nghiêm trọng"]
                    # Use radio for toggle-like experience (horizontal)
                    s_sev = st.radio("Mức độ", final_md_options, index=0, key="dlg_sev", horizontal=True)

                st.write("")
                st.markdown("---")
                
                # SUBMIT BUTTON
                if st.button("✅ THÊM VÀO DANH SÁCH", type="primary", use_container_width=True):
                    # Basic Validation
                    if not final_name:
                        st.warning("⚠️ Vui lòng nhập/chọn Tên lỗi!")
                        return
                    
                    # Add to buffer
                    st.session_state.buffer_errors.append({
                        "ten_loi": final_name,
                        "vi_tri": final_pos if final_pos else "",
                        "muc_do": s_sev,
                        "sl_loi": s_qty # Will be float or int based on input
                    })
                    
                    # Feedback 
                    st.session_state["success_msg"] = f"Đã thêm: {final_name}"
                    
                    # RESET FORM fields by deleting keys
                    keys_to_clear = ["dlg_ten_loi", "dlg_ten_loi_new", "dlg_vi_tri_sel", "dlg_vi_tri_txt", "dlg_qty_float", "dlg_qty_int", "dlg_sev"]
                    for k in keys_to_clear:
                        if k in st.session_state:
                             del st.session_state[k]
                    
                    # Rerun fragment to clear view
                    st.rerun()

            # Execute the fragment
            inner_defect_form()

            # Execute the fragment
            inner_defect_form()
            
        # --- VOICE INPUT DIALOG ---
        @st.dialog("🎤 Nhập lỗi bằng giọng nói")
        def open_voice_input_dialog():
            # --- MOBILE PERMISSION WORKAROUND ---
            # Trên mobile, lần đầu bấm ghi âm sẽ trigger popup "Cho phép truy cập Mic?"
            # Điều này gây ra lỗi ghi 0 giây. Giải pháp: Thêm bước "Sẵn sàng" để user biết.
            
            if "voice_mic_ready" not in st.session_state:
                st.session_state.voice_mic_ready = False
            
            if not st.session_state.voice_mic_ready:
                st.warning("""
                � **Lưu ý quan trọng cho Mobile:**
                
                Nếu đây là lần đầu ghi âm, khi bấm nút **"Start recording"** phía dưới:
                1. Trình duyệt sẽ hỏi **"Cho phép truy cập Microphone?"** → Bấm **Cho phép**.
                2. Sau đó bấm **"Start recording"** lần nữa để bắt đầu ghi âm thực sự.
                
                Đây là hành vi bình thường của trình duyệt di động.
                """)
                st.info("👇 Bấm nút bên dưới để bắt đầu (có thể cần bấm 2 lần nếu là lần đầu).")
            
            # 1. RECORDER (Native Streamlit)
            # Sử dụng st.audio_input (Available in Streamlit 1.40+) để fix lỗi mobile
            audio_file = st.audio_input("Nhấn để Ghi âm", key="voice_audio_input")
            
            audio_bytes = None
            if audio_file:
                audio_bytes = audio_file.read()
                # Mark as ready for future recordings in this session
                st.session_state.voice_mic_ready = True
                # st.audio_input đã có sẵn playback, không cần st.audio nữa
                
                # 2. ANALYZE BUTTON
                if st.button("✨ PHÂN TÍCH GIỌNG NÓI", type="primary", use_container_width=True):
                    with st.spinner("🤖 AI đang phân tích..."):
                        # Call service
                        ai_results, usage_info = process_audio_defect(audio_bytes, LIST_LOI, LIST_VI_TRI)
                        
                        if not ai_results:
                            st.warning("⚠️ Không tìm thấy lỗi nào hoặc không nghe rõ. Vui lòng thử lại.")
                        else:
                            st.session_state.voice_results = ai_results
                            # st.rerun() bỏ rerun để tránh đóng dialog
                            st.success("✅ Đã phân tích xong! Vui lòng kiểm tra kết quả bên dưới.")
                            
                            # Save usage info to persistent state
                            if usage_info:
                                st.session_state.voice_usage = usage_info
            
            # 3. SHOW RESULTS & CONFIRM
            if "voice_results" in st.session_state and st.session_state.voice_results:
                st.divider()
                st.markdown("##### 📋 Kết quả phân tích:")
                
                # Show Persistent Cost Info
                if "voice_usage" in st.session_state:
                     u = st.session_state.voice_usage
                     st.caption(f"💰 Chi phí: **{u.get('cost_vnd',0):.0f} VNĐ** | Tokens: {u.get('total_tokens',0)}")

                valid_items = []
                has_unknown = False
                
                # Render list for review
                for idx, item in enumerate(st.session_state.voice_results):
                    # STRICT CHECK: Must be in LIST_LOI
                    name_check = item.get("ten_loi")
                    is_not_in_list = name_check not in LIST_LOI
                    is_marked_unknown = name_check == "UNKNOWN_DEFECT"
                    
                    # Treating as unknown if explicitly marked OR not found in standard list
                    is_unknown = is_marked_unknown or is_not_in_list
                    
                    if is_unknown: 
                        has_unknown = True
                        # Preserve raw input reference if it was not already set
                        if is_not_in_list and not is_marked_unknown:
                            item["raw_input"] = name_check
                            item["ten_loi"] = "UNKNOWN_DEFECT" # Normalize status
                    
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        
                        # Defect Name Edit
                        if is_unknown:
                            c1.error(f"❓ Lỗi lạ: {item.get('raw_input', '')}")
                            new_name = c1.selectbox(f"Chọn tên lỗi đúng (Mục #{idx+1})", [""] + LIST_LOI, key=f"v_fix_{idx}")
                            if new_name:
                                item["ten_loi"] = new_name
                                item["raw_input"] = "" # Clear flag
                        else:
                            c1.markdown(f"**{item.get('ten_loi')}**")
                            
                        # Details
                        c1.caption(f"Vị trí: {item.get('vi_tri')} | Mức độ: {item.get('muc_do')}")
                        
                        # Quantity Edit
                        new_qty = c2.number_input("SL", value=float(item.get('sl_loi', 1)), key=f"v_qty_{idx}", min_value=0.1)
                        item['sl_loi'] = new_qty
                        
                        valid_items.append(item)

                if has_unknown:
                    st.warning("⚠️ Có lỗi chưa xác định (UNKNOWN). Vui lòng chọn tên lỗi chuẩn trong danh sách sổ xuống.")
                
                # CONFIRM BUTTON
                btn_disabled = any(x["ten_loi"] == "UNKNOWN_DEFECT" for x in st.session_state.voice_results)
                
                if st.button("✅ XÁC NHẬN THÊM VÀO LIST", type="primary", use_container_width=True, disabled=btn_disabled):
                    count = 0
                    for valid_item in valid_items:
                        if valid_item["ten_loi"] != "UNKNOWN_DEFECT":
                            st.session_state.buffer_errors.append(valid_item)
                            count += 1
                    
                    if count > 0:
                        count_msg = f"Đã thêm thành công {count} lỗi!"
                        cost_msg = ""
                        
                        # Add Cost Info to success message
                        if "voice_usage" in st.session_state:
                             u = st.session_state.voice_usage
                             cost_msg = f" (Chi phí: {u.get('cost_vnd',0):.0f} VNĐ)"
                             del st.session_state.voice_usage # Cleanup

                        st.session_state["success_msg"] = count_msg + cost_msg
                        del st.session_state.voice_results # Clear buffer
                        st.rerun()

        # --- MAIN UI: ADD BUTTONS ---
        col_manual, col_voice = st.columns([1, 1])
        with col_manual:
             if st.button("➕ NHẬP TAY", type="secondary", use_container_width=True):
                open_add_defect_dialog()
        
        with col_voice:
             if st.button("🎤 NHẬP GIỌNG NÓI", type="primary", use_container_width=True):
                open_voice_input_dialog()

        # --- FEEDBACK DISPLAY ---
        if st.session_state.get("success_msg"):
            st.toast(st.session_state["success_msg"], icon="✅")
            st.session_state["success_msg"] = "" 

        # --- BUFFER LIST RENDER ---
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
        
        # Prepare custom limits if enabled
        custom_limits = None
        if st.session_state.custom_sample_size:
            # We access the widget keys directly or variables if in scope.
            # Variables custom_major/custom_minor are in local scope from Top Section.
            # Assuming 'custom_major' is defined in the block above (it is).
             if 'custom_major' in locals() and 'custom_minor' in locals() and custom_major is not None:
                custom_limits = {'ac_major': custom_major, 'ac_minor': custom_minor}

        inspection_result, aql_details = evaluate_lot_quality(sl_lo, total_major, total_minor, custom_limits)
        
        if inspection_result == 'Pass':
            st.success("✅ **KẾT QUẢ: ĐẠT (PASS)** - Đủ điều kiện nhập kho!")
            if not st.session_state.buffer_errors: st.caption("ℹ️ Không phát hiện lỗi nào.")
            
            # Show used limits info
            eff_limits = aql_details.get('effective_limits', {})
            st.caption(f"Tiêu chuẩn: Major <= {eff_limits.get('ac_major')} | Minor <= {eff_limits.get('ac_minor')}")

            save_label = "💾 LƯU BIÊN BẢN KIỂM TRA (PASS)"
            save_btn_type = "primary"
        else:
            st.error("❌ **KẾT QUẢ: KHÔNG ĐẠT (FAIL)** - Cần lập phiếu NCR!")
            
            # Show diff
            eff_limits = aql_details.get('effective_limits', {})
            limit_major = eff_limits.get('ac_major', 0)
            limit_minor = eff_limits.get('ac_minor', 0)
            
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
        
        # Auto-suggest ID
        _, suggested_suffix = generate_next_ncr_id(dept_prefix)
        
        # Use dynamic key so it refreshes if prefix/month changes, but stable for typing
        suffix_key = f"ncr_suffix_{dept_prefix}_{curr_month}"
        
        ncr_suffix = c_ncr1.text_input(
            "Số đuôi NCR (xx)", 
            value=suggested_suffix,
            help=f"Gợi ý: {suggested_suffix}", 
            max_chars=3,
            key=suffix_key
        )
        if ncr_suffix:
            final_ncr_num = f"{dept_prefix}-{curr_month}-{ncr_suffix}"
            c_ncr2.markdown(f"👉 Mã phiếu: **{final_ncr_num}**")
        else:
            c_ncr2.warning("⬅️ Vui lòng nhập số đuôi phiếu NCR")
            
        mo_ta_loi = st.text_area("Mô tả lỗi chi tiết / Nguyên nhân", height=80)
    elif profile.has_aql and inspection_result == 'Pass':
        st.info("ℹ️ Mã phiếu Kiểm Đạt sẽ được hệ thống tự động tạo (VD: FIKD-01-XX).")
    
    # --- IMAGE UPLOAD (ALWAYS VISIBLE) ---
    st.markdown("##### 📷 Hình ảnh bằng chứng")
    uploaded_images = st.file_uploader("Tải lên hình ảnh", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True, label_visibility="collapsed")
    
    # --- NÚT LƯU CUỐI CÙNG ---
    if st.button(save_label, type=save_btn_type, use_container_width=True):
        if (not profile.has_aql or inspection_result == 'Fail') and not final_ncr_num:
            st.error("⚠️ Vui lòng nhập SỐ ĐUÔI NCR trước khi lưu!")
            st.stop()
            
        # Validate Duplicate ID
        if (not profile.has_aql or inspection_result == 'Fail'):
             if is_ncr_id_exists(final_ncr_num):
                 st.error(f"⚠️ Mã phiếu {final_ncr_num} đã tồn tại! Vui lòng kiểm tra lại.")
                 st.stop()
        
        # Auto-Generate ID for Pass
        if profile.has_aql and inspection_result == 'Pass':
            final_ncr_num = generate_next_pass_id(dept_prefix)
        
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
                    
                current_status = "hoan_thanh" if inspection_result == 'Pass' else get_initial_status(profile.code)
                
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
                    if inspection_result == 'Pass':
                        st.success(f"✅ Đã lưu thành công! Mã phiếu Kiểm Đạt của bạn là: **{final_ncr_num}**")
                    else:
                        st.success(f"✅ Đã lưu thành công {success_count} dòng! ({inspection_result})")
                    st.session_state.buffer_errors = []
                    st.session_state.header_locked = False
                else:
                    st.error("Lỗi khi lưu dữ liệu vào Sheet.")
        except Exception as e:
            st.error(f"System Error: {e}")
