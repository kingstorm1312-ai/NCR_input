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
    if st.button("🔄 Làm mới", help="Clear cache và tải lại dữ liệu mới nhất"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Admin can act as any role
if user_role == 'admin':
    st.info("🔑 Admin Mode: Chọn role để xem NCR cần phê duyệt")
    selected_role = st.selectbox(
        "Xem với quyền:",
        ['truong_ca', 'truong_bp', 'qc_manager', 'director', 'bgd_tan_phu']
    )
else:
    selected_role = user_role

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    df_original, df_grouped, filter_status = get_pending_approvals(
        user_role, 
        user_dept, 
        admin_selected_role=selected_role if user_role == 'admin' else None
    )

if filter_status is None:
    st.error("Lỗi: Không tìm thấy trạng thái phê duyệt cho Role này.")
    st.stop()

# --- DISPLAY STATUS INFO ---
display_status = get_status_display_name(filter_status)
st.info(f"Đang hiển thị phiếu trạng thái: **{display_status}**")

if df_grouped.empty:
    st.success("🎉 Không có phiếu nào cần phê duyệt!")
else:
    count = len(df_grouped)
    st.markdown(f"**Tìm thấy {count} phiếu cần xử lý**")
    
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
                                    img_cols[j].image(img_url, use_container_width=True)
                                    img_cols[j].link_button("🔍 Phóng to", img_url, use_container_width=True)
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
                # Get original rows for this ticket
                ticket_rows = df_original[df_original['so_phieu'] == so_phieu]
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
                        use_container_width=True,
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
                
                if st.button(confirm_label, key=f"btn_approve_{so_phieu}", type="primary", use_container_width=True):
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
                if st.button("❌ TỪ CHỐI / TRẢ VỀ", key=f"btn_reject_{so_phieu}", type="secondary", use_container_width=True):
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
