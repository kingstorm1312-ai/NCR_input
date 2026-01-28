import streamlit as st
import pandas as pd
import gspread
import json
import sys
import os
import re
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import (
    get_status_display_name,
    get_status_color,
    ROLE_TO_STATUS,
    STATUS_FLOW,
    REJECT_ESCALATION,
    init_gspread,
    get_now_vn,
    get_next_status
)
from core.services.approval_service import (
    get_pending_approvals,
    approve_ncr,
    reject_ncr
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Phê Duyệt NCR", page_icon="✍️", layout="centered", initial_sidebar_state="auto")

# --- MOBILE NAVIGATION HELPER ---
# --- MOBILE NAVIGATION HELPER ---
# Styles handled by ui_nav
pass
# --- REMOVED OLD SIDEBAR CODE ---

# --- AUTHENTICATION CHECK ---
from core.auth import require_roles
user_info = require_roles(['truong_ca', 'truong_bp', 'qc_manager', 'director', 'bgd_tan_phu'])
user_role = user_info.get("role")
user_name = user_info.get("name")
user_dept = user_info.get("department")

# --- GOOGLE SHEETS CONNECTION ---


# --- FLASH MESSAGE CHECK (Must be early) ---
if 'flash_msg' in st.session_state and st.session_state.flash_msg:
    msg_type = st.session_state.flash_msg.get('type', 'success')
    content = st.session_state.flash_msg.get('content', '')
    if msg_type == 'success':
        st.success(content)
        st.balloons()
    elif msg_type == 'error':
        st.error(content)
    elif msg_type == 'warning':
        st.warning(content)
    # Clear after showing
    st.session_state.flash_msg = None

# --- HEADER ---
st.title("✍️ Phê Duyệt NCR")
st.caption(f"Xin chào **{user_name}** - Role: **{user_role.upper()}**")

# Clear cache button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Làm mới", help="Clear cache và tải lại dữ liệu mới nhất", key="btn_refresh_cache"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Admin can act as any role
if user_role == 'admin':
    st.info("🔑 Admin Mode: Chọn role để xem NCR cần phê duyệt")
    selected_role = st.selectbox(
        "Xem với quyền:",
        ['truong_ca', 'truong_bp', 'qc_manager', 'director', 'bgd_tan_phu'],
        key="admin_role_selector"
    )
else:
    selected_role = user_role

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    # We pass 'all' as user_dept to fetch all departments for in-memory filtering.
    df_original, df_grouped, filter_status = get_pending_approvals(
        user_role, 
        'all', 
        admin_selected_role=selected_role if user_role == 'admin' else None
    )

if filter_status is None:
    st.error("Lỗi: Không tìm thấy trạng thái phê duyệt cho Role này.")
    st.stop()

# --- DERIVE DEPARTMENT LOGIC (Minimal Patch) ---
def derive_dept_from_ticket(ticket):
    """
    Derive department code from ticket number prefix.
    Rule: Match longer prefixes first.
    """
    if not isinstance(ticket, str) or not ticket:
        return 'unknown'
    
    t = ticket.strip().upper()
    # Normalize: remove extra spaces, unify dashes
    t = re.sub(r'\s*-\s*', '-', t)
    
    # Mapping Rules (Longest Match First)
    MAPPING = [
        ('X2-TR', 'trang_cat'), # Map 'Tráng' to shared dept
        ('X2-CA', 'trang_cat'), # Map 'Cắt' to shared dept
        ('DVTP', 'tp_dau_vao'),
        ('NPLDV', 'dv_cuon'),   # Spec says NPLDV -> dv_cuon
        ('DVNPL', 'dv_npl'),
        ('XG', 'in_xuong_d'),   # Spec say XG -> xuong_in (file code is in_xuong_d)
        ('CXA', 'cat_ban'),
        ('X4', 'may_n4'),
        ('X3', 'may_a2'),
        ('XA', 'may_p2'),
        ("I'", 'may_i'), 
        ('I’', 'may_i'), # Handle curly quote
        ('FI', 'fi')
    ]
    
    for prefix, dept in MAPPING:
        if t.startswith(prefix):
            return dept
            
    return 'unknown'

# Apply Derivation if data exists
if not df_grouped.empty:
    # Ensure so_phieu column exists
    ticket_col = 'so_phieu' if 'so_phieu' in df_grouped.columns else ('so_phieu_ncr' if 'so_phieu_ncr' in df_grouped.columns else None)
    
    if ticket_col:
        # Debug info
        # st.caption("Dept source = derived from ticket prefix") 
        
        # Apply to grouped
        df_grouped['bo_phan_derived'] = df_grouped[ticket_col].apply(derive_dept_from_ticket)
        # Apply to original (for detail view filtering if needed, though details usually filtered by so_phieu)
        if not df_original.empty and ticket_col in df_original.columns:
             df_original['bo_phan_derived'] = df_original[ticket_col].apply(derive_dept_from_ticket)
             
        # Use derived column as main 'bo_phan' for filtering logic below
        # We don't overwrite original 'bo_phan' if it exists to preserve raw data integrity, 
        # but for filtering UI we use derived.
        filter_col = 'bo_phan_derived'
    else:
        filter_col = None
else:
    filter_col = None

# --- DEPARTMENT FILTER (Mobile-first) ---
if not df_grouped.empty and filter_col:
    # Get unique departments from data
    available_depts = sorted(df_grouped[filter_col].unique().tolist())
    
    # Move 'unknown' to end
    if 'unknown' in available_depts:
        available_depts.remove('unknown')
        available_depts.append('unknown')
    
    # Initialize filter selection in session state
    filter_key = f"filter_depts_{selected_role}"
    if filter_key not in st.session_state:
        # Default logic
        default_selection = []
        if user_role == 'admin':
            default_selection = available_depts # Admin sees all by default
        elif user_role == 'truong_ca' and user_dept:
             # Truong Ca sees their dept by default if available
             if user_dept in available_depts:
                 default_selection = [user_dept]
        
        st.session_state[filter_key] = default_selection
    
    # Ensure session state values are still valid
    st.session_state[filter_key] = [d for d in st.session_state[filter_key] if d in available_depts]

    # Render Filter UI
    f_col1, f_col2 = st.columns([3, 1])
    with f_col1:
        selected_depts = st.multiselect(
            "🏢 Lọc theo khâu:",
            options=available_depts,
            key=filter_key,
            help="Chọn khâu để lọc danh sách"
        )
    # Calculate default for reset
    reset_to_default = []
    if user_role == 'admin':
        reset_to_default = available_depts
    elif user_role == 'truong_ca' and user_dept and user_dept in available_depts:
        reset_to_default = [user_dept]

    # Callback function
    def reset_filter_callback():
        st.session_state[filter_key] = reset_to_default

    with f_col2:
        st.write("") # Spacer for alignment
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        st.button("🗑️ Xóa lọc", width="stretch", help="Reset về mặc định", on_click=reset_filter_callback)

    # Apply in-memory filtering
    if selected_depts:
        df_grouped = df_grouped[df_grouped[filter_col].isin(selected_depts)]
        # Filter original rows as well to keep consistency if needed later
        if not df_original.empty and filter_col in df_original.columns:
            df_original = df_original[df_original[filter_col].isin(selected_depts)]

# --- DISPLAY STATUS INFO ---
display_status = get_status_display_name(filter_status)
st.info(f"Đang hiển thị phiếu trạng thái: **{display_status}**")

if df_grouped.empty:
    st.success("🎉 Không có phiếu nào khớp với bộ lọc!")
else:
    count = len(df_grouped)
    st.markdown(f"**Tìm thấy {count} phiếu cần xử lý**")
    
    # --- FRAGMENT DEFINITION (OUTSIDE LOOP) ---
    if hasattr(st, "fragment"):
        fragment_decorator = st.fragment
    else:
        fragment_decorator = lambda func: func

    @fragment_decorator
    def render_dnxl_form_fragment(so_phieu, row, df_original, user_name, dnxl_service):
        """
        Render the DNXL creation form as a fragment to isolate reruns.
        """
        # --- MASTER INPUTS ---
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            target_scope = st.text_input("Số lượng yêu cầu (Total Qty)*", placeholder="VD: 5000, 100 cuộn...", key=f"target_scope_{so_phieu}")
        with c_m2:
            deadline_date = st.date_input("Hạn xử lý (Deadline)", key=f"deadline_{so_phieu}")
        
        handling_instruction = st.text_area("Hướng dẫn xử lý chung (Instruction)*", placeholder="Hướng dẫn quy cách xử lý...", height=80, key=f"instruction_{so_phieu}")
        
        # --- DNXL BUFFER INIT ---
        buffer_key = f"dnxl_buffer_{so_phieu}"
        if buffer_key not in st.session_state:
            default_defect = row.get('ten_loi', '') or row.get('mo_ta_loi', '')
            # Default Quantity Logic: If user says "don't need input", we default to 0 or 1.
            default_qty = row.get('sl_loi', 0)
            
            if default_defect:
                st.session_state[buffer_key] = [{
                    "Tên Lỗi": str(default_defect),
                    "SL Cần Xử Lý": int(default_qty) if pd.notna(default_qty) else 0
                }]
            else:
                st.session_state[buffer_key] = []

        # --- DIALOG DEFINITION ---
        @st.dialog("➕ Thêm lỗi xử lý")
        def open_add_dnxl_dialog():
            available_defects = []
            # Use passed df_original
            ticket_rows = df_original[df_original['so_phieu'] == so_phieu]
            if not ticket_rows.empty:
                available_defects = ticket_rows['ten_loi'].unique().tolist()
            
            entry_mode = st.radio("Cách nhập:", ["Chọn từ NCR", "Nhập mới"], horizontal=True, label_visibility="collapsed")
            
            # Safe Guard: Check if data available
            if df_original is None or df_original.empty:
                st.warning("⚠️ Không tải được dữ liệu gốc. Vui lòng nhập thủ công.")
                entry_mode = "Nhập mới"
            
            if entry_mode == "Chọn từ NCR" and available_defects:
                 d_name = st.selectbox("Tên lỗi", available_defects, key=f"sel_defect_{so_phieu}")
            else:
                 d_name = st.text_input("Tên lỗi", placeholder="Nhập tên lỗi...", key=f"txt_defect_{so_phieu}")
            
            if st.button("Thêm vào danh sách", type="primary", width="stretch", key=f"btn_add_confirm_{so_phieu}"):
                if not d_name:
                    st.error("Vui lòng nhập tên lỗi!")
                else:
                    st.session_state[buffer_key].append({
                        "Tên Lỗi": d_name,
                        "SL Cần Xử Lý": 0
                    })
                    st.rerun()

        # --- DISPLAY LIST ---
        if st.session_state[buffer_key]:
            for idx, item in enumerate(st.session_state[buffer_key]):
                c_l1, c_l2 = st.columns([8, 1])
                with c_l1:
                    st.markdown(f"**{item['Tên Lỗi']}**")
                    # Hide Qty display
                with c_l2:
                    if st.button("🗑️", key=f"del_dnxl_{so_phieu}_{idx}", help="Xóa dòng này"):
                        st.session_state[buffer_key].pop(idx)
                        st.rerun()
            st.divider()
        else:
            st.info("Danh sách lỗi đang trống. Vui lòng thêm lỗi!")

        # --- ADD BUTTON ---
        if st.button("➕ THÊM LỖI", key=f"btn_add_dnxl_{so_phieu}", width="stretch"):
            open_add_dnxl_dialog()
        
        st.write("") # Spacer

        # --- SUBMIT BUTTON ---
        submit_val = st.button("💾 LƯU PHIẾU DNXL", type="primary", key=f"submit_dnxl_{so_phieu}")

        if submit_val:
            # Validation
            if not target_scope.strip():
                st.error("⚠️ Vui lòng nhập Phạm vi xử lý!")
                return 
                
            if not handling_instruction.strip():
                st.error("⚠️ Vui lòng nhập Hướng dẫn xử lý!")
                return
                
            current_buffer = st.session_state.get(buffer_key, [])
            if not current_buffer:
                 st.error("⚠️ Vui lòng nhập ít nhất 1 dòng lỗi chi tiết!")
                 return
            
            valid_details = pd.DataFrame(current_buffer)
            
            # Ensure SL column exists even if 0
            if "SL Cần Xử Lý" not in valid_details.columns:
                valid_details["SL Cần Xử Lý"] = 0
                
            form_header = {
                "target_scope": target_scope,
                "deadline": deadline_date,
                "handling_instruction": handling_instruction
            }
            
            with st.spinner("Đang tạo phiếu DNXL..."):
                success_dnxl, res_dnxl = dnxl_service.create_dnxl(row, form_header, valid_details, user_name)
                
                if success_dnxl:
                    st.success(f"✅ Đã tạo DNXL thành công! ID: {res_dnxl}")
                    st.session_state.pop(buffer_key, None)
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Lỗi tạo DNXL: {res_dnxl}")

    # --- OPTIMIZATION: PRE-GROUP DETAILS ---
    # Group df_original by so_phieu once to avoid filtering in loop
    details_map = {}
    if not df_original.empty and 'so_phieu' in df_original.columns:
        # Create a dictionary of DataFrames for O(1) access
        # Note: groupby is faster than filtering N times
        details_map = {k: v for k, v in df_original.groupby('so_phieu')}

    # --- RENDER TICKETS ---
    for _, row in df_grouped.iterrows():
        # EXTRACT DATA SAFELY
        so_phieu = row.get('so_phieu', 'Unknown')
        trang_thai = row.get('trang_thai', 'Unknown')
        ngay_lap = row.get('ngay_lap', 'N/A')
        # Handle nguoi_lap_phieu explicitly
        nguoi_lap = row.get('nguoi_lap_phieu', 'N/A')
        tong_loi = row.get('sl_loi', 0)
        
        status_name = get_status_display_name(trang_thai)
        expander_label = f"📋 {so_phieu} | {status_name} | 👤 {nguoi_lap} | ⚠️ {tong_loi} lỗi"
        
        with st.expander(expander_label, expanded=False):
            # Info grid
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"📅 **Ngày tạo:** {ngay_lap}")
            with col2:
                if 'bo_phan' in row:
                    st.write(f"🏢 **Bộ phận:** {str(row['bo_phan']).upper()}")
            
            # Display Note/Message (from ly_do_tu_choi)
            if 'ly_do_tu_choi' in row and row['ly_do_tu_choi']:
                note = str(row['ly_do_tu_choi']).strip()
                if note:
                    st.info(f"📩 **Tin nhắn:** {note}")
            
            # Error details in expander
            with st.expander("🔍 Xem chi tiết & Hình ảnh", expanded=True):
                # --- HÌNH ẢNH (Move to Top) ---
                st.markdown("#### 📷 Hình ảnh minh họa")
                hinh_anh_val = row.get('hinh_anh', "")
                if pd.notna(hinh_anh_val) and str(hinh_anh_val).strip():
                    img_list = re.findall(r'(https?://[^\s]+)', str(hinh_anh_val))
                    if img_list:
                        # Display images in a grid
                        cols_per_row = 3
                        for i in range(0, len(img_list), cols_per_row):
                            img_cols = st.columns(cols_per_row)
                            for j in range(cols_per_row):
                                if i + j < len(img_list):
                                    img_url = img_list[i+j]
                                    img_cols[j].image(img_url, width="stretch")
                                    img_cols[j].link_button("🔍 Phóng to", img_url, width="stretch")
                        st.markdown("**🔗 Link ảnh trực tiếp:**")
                        for idx, url in enumerate(img_list):
                            st.markdown(f"- [Chi tiết ảnh {idx+1}]({url})")
                    else:
                        st.info("ℹ️ Phiếu này không có hình ảnh minh họa.")
                else:
                    st.info("ℹ️ Phiếu này không có hình ảnh minh họa.")

                st.markdown("---")

                # Header Info Grid
                st.markdown("#### 📄 Thông tin chung")
                ca1, ca2 = st.columns(2)
                with ca1:
                    st.write(f"📁 **Hợp đồng:** {row.get('hop_dong', 'N/A')}")
                    st.write(f"🔢 **Mã vật tư:** {row.get('ma_vat_tu', 'N/A')}")
                    st.write(f"🔄 **Số lần:** {row.get('so_lan', 1)}")
                    st.write(f"📦 **Tên sản phẩm:** {row.get('ten_sp', 'N/A')}")
                    st.write(f"🏷️ **Phân loại:** {row.get('phan_loai', 'N/A')}")
                with ca2:
                    st.write(f"🏢 **Nguồn gốc/NCC:** {row.get('nguon_goc', 'N/A')}")
                    st.write(f"🔢 **SL Kiểm:** {row.get('sl_kiem', 0)}")
                    st.write(f"📦 **SL Lô:** {row.get('sl_lo_hang', 0)}")
                    st.write(f"🕒 **Cập nhật cuối:** {row.get('thoi_gian_cap_nhat', 'N/A')}")
                
                if row.get('mo_ta_loi'):
                    st.markdown(f"📝 **Mô tả lỗi / Quy cách:**\n{row.get('mo_ta_loi')}")
                
                st.markdown("---")
                
                # --- TIMELINE ĐỀ XUẤT GIẢI PHÁP ---
                st.markdown("#### 💡 Chuỗi xử lý tức thời")
                has_any_solution = False
                
                # Biện pháp Trưởng BP
                if row.get('bien_phap_truong_bp'):
                    has_any_solution = True
                    st.info(f"**👔 Trưởng BP - Biện pháp xử lý tức thời:**\n{row['bien_phap_truong_bp']}")
                
                # Hướng giải quyết QC Manager
                if row.get('huong_giai_quyet'):
                    has_any_solution = True
                    st.success(f"**🔬 QC Manager - Hướng giải quyết:**\n{row['huong_giai_quyet']}")
                
                # Hướng xử lý Giám đốc
                if row.get('huong_xu_ly_gd'):
                    has_any_solution = True
                    st.warning(f"**👨‍💼 Giám đốc - Hướng xử lý:**\n{row['huong_xu_ly_gd']}")
                
                # --- HÀNH ĐỘNG KHẮC PHỤC (Timeline) ---
                if row.get('kp_status') and row.get('kp_status') != 'none':
                    has_any_solution = True
                    kp_status = row['kp_status']
                    kp_by = row.get('kp_assigned_by', '').upper()
                    kp_to = row.get('kp_assigned_to', '').upper()
                    kp_msg = row.get('kp_message', '')
                    kp_dl = row.get('kp_deadline', '')
                    kp_res = row.get('kp_response', '')
                    
                    st.markdown("---")
                    st.subheader("🛠️ Hành động khắc phục")
                    st.write(f"**Trạng thái:** {kp_status.upper()}")
                    st.write(f"**Người giao:** {kp_by} → **Người nhận:** {kp_to}")
                    st.info(f"**Nội dung yêu cầu:**\n{kp_msg}")
                    st.markdown(f"📅 **Hạn chót:** :red[**{kp_dl}**]")
                    
                    if kp_res:
                        st.success(f"**Phản hồi hoàn thành:**\n{kp_res}")
                    
                    # Deadline warning
                    if kp_status == 'active' and kp_dl:
                        try:
                            deadline_dt = pd.to_datetime(kp_dl).date()
                            today = datetime.now().date()
                            if today > deadline_dt:
                                st.error(f"⚠️ QUÁ HẠN: Task này đã trễ hạn { (today - deadline_dt).days } ngày!")
                        except:
                            pass

                if not has_any_solution:
                    st.caption("_Chưa có đề xuất xử lý từ các cấp quản lý._")
                
                st.markdown("---")
                st.markdown("#### ❌ Mô tả sự không phù hợp")
                # Get original rows for this ticket using optimized map
                ticket_rows = details_map.get(so_phieu, pd.DataFrame())
                if not ticket_rows.empty:
                    display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'don_vi_tinh', 'md_loi']
                    column_config = {
                        "ten_loi": "Tên lỗi",
                        "vi_tri_loi": "Vị trí",
                        "sl_loi": "SL",
                        "don_vi_tinh": "ĐVT",
                        "md_loi": "Mức độ"
                    }
                    available_cols = [col for col in display_cols if col in ticket_rows.columns]
                    st.dataframe(
                        ticket_rows[available_cols].rename(columns=column_config),
                        width="stretch",
                        hide_index=True
                    )
            
            # --- ACTION SECTION ---
            st.write("")  # Spacer
            st.divider()
            
            # --- INPUT SOLUTIONS BASED ON ROLE ---
            bp_solution = None
            qc_solution = None
            director_solution = None
            
            if selected_role == 'truong_bp':
                pre_fill_bp = row.get('bien_phap_truong_bp', '')
                bp_solution = st.text_area(
                    "📋 Biện pháp xử lý tức thời (Trưởng BP):",
                    key=f"bp_sol_{so_phieu}",
                    value=pre_fill_bp,
                    help="Bắt buộc nhập trước khi phê duyệt"
                )
            
            if selected_role == 'qc_manager':
                pre_fill_qc = row.get('huong_giai_quyet', '')
                qc_solution = st.text_area(
                    "🔬 Hướng giải quyết (QC Manager):",
                    key=f"qc_sol_{so_phieu}",
                    value=pre_fill_qc,
                    help="Bắt buộc nhập trước khi phê duyệt"
                )
            
            if selected_role == 'director':
                pre_fill_dir = row.get('huong_xu_ly_gd', '')
                director_solution = st.text_area(
                    "👨‍💼 Hướng xử lý (Giám đốc):",
                    key=f"dir_sol_{so_phieu}",
                    value=pre_fill_dir,
                    help="Bắt buộc nhập trước khi phê duyệt"
                )
            
            # Logic for NEXT STATUS based on Flow (Dynamic)
            next_status = get_next_status(trang_thai, row.get('bo_phan', ''))
            
            # --- START QC MANAGER FLEXIBLE ROUTING ---
            director_assignee = None
            if selected_role == 'qc_manager':
                st.write("---")
                st.markdown("### 🔀 Điều hướng phê duyệt")
                routing_option = st.radio(
                    "Chọn cấp phê duyệt tiếp theo:",
                    ["Chuyển Giám đốc (Director)", "Chuyển BGD Tân Phú", "✅ Hoàn thành ngay (Kết thúc)"],
                    key=f"routing_{so_phieu}",
                    horizontal=False
                )
                
                target_role_key = 'director'
                target_label = "Giám đốc"
                
                if routing_option == "Chuyển Giám đốc (Director)":
                   next_status = 'cho_giam_doc'
                   target_role_key = 'director'
                   target_label = "Giám đốc"
                   
                elif routing_option == "Chuyển BGD Tân Phú":
                   next_status = 'cho_bgd_tan_phu'
                   target_role_key = 'bgd_tan_phu'
                   target_label = "BGD Tân Phú"
                   
                elif routing_option == "✅ Hoàn thành ngay (Kết thúc)":
                   next_status = 'hoan_thanh'
                
                # Dynamic Director Assignment (Only if sending to Director)
                if next_status == 'cho_giam_doc':
                    directors = {
                        "director": "Giám Đốc (Mặc định)",
                        "giam_doc_1": "Giám Đốc 1", # Add real users if needed
                        "giam_doc_2": "Giám Đốc 2"
                    }
                    # For now just informational
                    # st.info(f"Phiếu sẽ được chuyển đến: {target_label}")
            # --- END QC MANAGER FLEXIBLE ROUTING ---

            # --- ACTION BUTTONS ---
            st.write("")
            col_b1, col_b2 = st.columns(2)
            
            with col_b1:
                confirm_label = "✅ PHÊ DUYỆT"
                if selected_role == 'qc_manager' and next_status == 'hoan_thanh':
                     confirm_label = "✅ KẾT THÚC PHIẾU"
                
                if st.button(confirm_label, key=f"btn_approve_{so_phieu}", type="primary", width="stretch"):
                    # Validation
                    if selected_role == 'truong_bp' and not str(bp_solution).strip():
                        st.error("⚠️ Vui lòng nhập 'Biện pháp xử lý tức thời'!")
                    elif selected_role == 'qc_manager' and not str(qc_solution).strip():
                        st.error("⚠️ Vui lòng nhập 'Hướng giải quyết'!")
                    elif selected_role == 'director' and not str(director_solution).strip():
                        st.error("⚠️ Vui lòng nhập 'Hướng xử lý'!")
                    else:
                        # Prepare data to update
                        updates = {}
                        if bp_solution: updates['bien_phap_truong_bp'] = bp_solution
                        if qc_solution: updates['huong_giai_quyet'] = qc_solution
                        if director_solution: updates['huong_xu_ly_gd'] = director_solution
                        
                        # Add approver timestamp/user
                        approver_col = ROLE_TO_STATUS.get(selected_role, 'unknown') # map to status? No
                        # better mapping in helper: ROLE_TO_APPROVER_COLUMN
                        
                        # Execute Update
                        with st.spinner("Đang xử lý..."):
                            success, msg = approve_ncr(
                                so_phieu, 
                                selected_role,
                                user_name,
                                next_status,
                                solutions={
                                    'bp_solution': bp_solution,
                                    'qc_solution': qc_solution,
                                    'director_solution': director_solution
                                }
                            )
                            if success:
                                st.session_state.flash_msg = {'type': 'success', 'content': f"Đã phê duyệt phiếu {so_phieu} thành công!"}
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(f"Lỗi: {msg}")

            with col_b2:
                if st.button("❌ TỪ CHỐI / TRẢ VỀ", key=f"btn_reject_{so_phieu}", type="secondary", width="stretch"):
                    # Ask for reason (Simplest way: use the text area if available or new dialog)
                    # For rejection, we usually require a reason.
                    # Since we can't pop up input easily in Streamlit loop without rerun, 
                    # we demand the user to fill the 'Solution' box with the rejection reason OR add a specific input.
                    
                    # Better UX: Expander for rejection
                    st.session_state[f"show_reject_{so_phieu}"] = True
            
            if st.session_state.get(f"show_reject_{so_phieu}", False):
                with st.form(key=f"reject_form_{so_phieu}"):
                    reject_reason = st.text_area("Lý do từ chối/trả về:", placeholder="Nhập lý do...")
                    submit_reject = st.form_submit_button("Xác nhận Từ chối")
                    
                    if submit_reject:
                        if not reject_reason.strip():
                            st.error("Vui lòng nhập lý do từ chối!")
                        else:
                            # Logic reject
                            prev_status = REJECT_ESCALATION.get(trang_thai, 'draft')
                            
                            with st.spinner("Đang trả phiếu về..."):
                                success, msg = reject_ncr(
                                    so_phieu,
                                    selected_role,
                                    user_name,
                                    trang_thai,
                                    reject_reason
                                )
                                if success:
                                    st.session_state.flash_msg = {'type': 'warning', 'content': f"Đã trả phiếu {so_phieu} về."}
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error(msg)

            # --- DNXL SECTION INTEGRATION (MASTER-DETAIL UPGRADE) ---
            from core.services import dnxl_service
            
            st.write("")
            st.divider()
            st.markdown("#### 📋 Quản Lý Đề Nghị Xử Lý (DNXL)")
            
            # 1. Display list of created DNXLs
            df_dnxl = dnxl_service.get_dnxl_by_ncr(so_phieu)
            if not df_dnxl.empty:
                # Add Download Button for each DNXL
                from core.services import export_service
                
                # Show main table
                st.dataframe(
                    df_dnxl[["dnxl_id", "target_scope", "status", "deadline", "created_by"]],
                    width="stretch",
                    hide_index=True
                )
                
                # Export Buttons
                st.markdown("⬇️ **Tải phiếu DNXL:**")
                
                # --- OPTIMIZATION START: Batch Fetch Details (If not already fetched) ---
                if 'all_details_map' not in locals():
                    with st.spinner("Đang chuẩn bị dữ liệu tải xuống..."):
                         all_details_map = dnxl_service.get_all_dnxl_details_map()
                # --- OPTIMIZATION END ---
                
                cols_dl = st.columns(min(len(df_dnxl), 4))
                for idx, (i, d_row) in enumerate(df_dnxl.iterrows()):
                    with cols_dl[idx % 4]:
                        dnxl_val = d_row.to_dict()
                        
                        # Get Details from MAP (Fast)
                        details_val = all_details_map.get(str(d_row['dnxl_id']), pd.DataFrame())
                        
                        # Generate EXCEL (Updated)
                        # Optimization Note: Generating Excel bytes for ALL buttons is still heavy if list is long.
                        # But with details cached, it's just local processing.
                        excel_file = export_service.generate_dnxl_docx(row, dnxl_val, details_val)
                        
                        if excel_file:
                            st.download_button(
                                label=f"📊 Tải Excel {d_row['dnxl_id']}",
                                data=excel_file,
                                file_name=f"{d_row['dnxl_id']}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_xlsx_{d_row['dnxl_id']}"
                            )
                        
                        # MANUAL COMPLETE BUTTON (OFFLINE PROCESS)
                        # Only for QC Manager and if not already completed/waiting review
                        if selected_role == 'qc_manager' and d_row['status'] not in ['hoan_thanh', 'cho_duyet_ket_qua']:
                            if st.button("✅ Hoàn tất", key=f"force_done_{d_row['dnxl_id']}", help="Bấm vào đây nếu phiếu đã xử lý offline", width="stretch"):
                                ok, msg = dnxl_service.force_complete_dnxl(d_row['dnxl_id'], user_name)
                                if ok:
                                    st.success("Đã hoàn tất!"); st.rerun()
                                else:
                                    st.error(msg)
            else:
                st.caption("Chưa có phiếu DNXL nào cho NCR này.")
            
            # 2. Create New DNXL Form (Master-Detail)
            # ONLY FOR QC MANAGER
            if selected_role == 'qc_manager':
                with st.expander("➕ Tạo Phiếu Đề Nghị Xử Lý Mới"):
                    st.info("💡 Nhập thông tin chung và danh sách lỗi chi tiết cần xử lý.")
                    render_dnxl_form_fragment(so_phieu, row, df_original, user_name, dnxl_service)

            # --- [SECTION: QC REVIEW WORKER RESULTS] ---
            # ONLY FOR QC MANAGER
            if selected_role == 'qc_manager':
                # Filter for tickets waiting for review
                pending_review_df = df_dnxl[df_dnxl['status'] == 'cho_duyet_ket_qua'] if not df_dnxl.empty else pd.DataFrame()
                
                if not pending_review_df.empty:
                    st.write("")
                    st.info(f"🔔 Cần duyệt: {len(pending_review_df)} phiếu đã xử lý xong.")
                    
                    # --- OPTIMIZATION START: Batch Fetch Details ---
                    with st.spinner("Đang tải chi tiết các phiếu..."):
                         all_details_map = dnxl_service.get_all_dnxl_details_map()
                    # --- OPTIMIZATION END ---

                    for i, p_row in pending_review_df.iterrows():
                        with st.container(border=True):
                            st.markdown(f"##### 🛡️ Duyệt KQ: `{p_row['dnxl_id']}`")
                            
                            # 1. Show Worker Report
                            w_c1, w_c2 = st.columns([2, 1])
                            with w_c1:
                                st.write(f"👷 **Người làm:** {p_row.get('claimed_by', 'N/A')}")
                                st.success(f"💬 **Phản hồi:** {p_row.get('worker_response', '(Không có)')}")
                            with w_c2:
                                imgs = str(p_row.get('worker_images', ''))
                                if imgs:
                                    st.markdown(f"📸 **Có ảnh báo cáo**")
                                    with st.expander("Xem ảnh"):
                                        for url in imgs.split('\n'):
                                            if url.strip(): st.write(f"- {url}")

                            # 2. Show Detail Quantities (Lookup from Map)
                            dnxl_id_str = str(p_row['dnxl_id'])
                            details_rev = all_details_map.get(dnxl_id_str, pd.DataFrame())
                            
                            if not details_rev.empty:
                                st.dataframe(
                                    details_rev[["defect_name", "qty_assigned", "qty_fixed", "qty_fail", "worker_note"]],
                                    column_config={
                                        "defect_name": "Lỗi",
                                        "qty_assigned": "Giao",
                                        "qty_fixed": "Đã sửa",
                                        "qty_fail": "Hỏng",
                                        "worker_note": "Ghi chú xưởng"
                                    },
                                    hide_index=True,
                                    width="stretch"
                                )
                            
                            # 3. Approve/Reject Actions
                            btn_c1, btn_c2 = st.columns(2)
                            with btn_c1:
                                if st.button("✅ DUYỆT OK", key=f"appr_{p_row['dnxl_id']}", type="primary", width="stretch"):
                                    ok, msg = dnxl_service.qc_review_dnxl(p_row['dnxl_id'], 'approve', "QC Accepted")
                                    if ok:
                                        st.success("Đã duyệt!"); st.rerun()
                                    else:
                                        st.error(msg)
                            with btn_c2:
                                with st.popover("❌ TRẢ LẠI", width="stretch"):
                                    reason = st.text_area("Lý do trả lại:", key=f"rej_rs_{p_row['dnxl_id']}")
                                    if st.button("Xác nhận Trả", key=f"cf_rej_{p_row['dnxl_id']}"):
                                        if reason:
                                            ok, msg = dnxl_service.qc_review_dnxl(p_row['dnxl_id'], 'reject', reason)
                                            if ok: st.rerun()
                                            else: st.error(msg)
                                        else:
                                            st.error("Cần nhập lý do!")



