import streamlit as st
import pandas as pd
import gspread
import json
import sys
import os
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ncr_helpers import (
    load_ncr_data_with_grouping,
    update_ncr_status,
    get_status_display_name,
    get_status_color,
    ROLE_TO_STATUS,
    STATUS_FLOW,
    REJECT_ESCALATION
)

# --- PAGE SETUP ---
st.set_page_config(page_title="Phê Duyệt NCR", page_icon="✍️", layout="centered", initial_sidebar_state="auto")

# --- MOBILE NAVIGATION HELPER ---
st.markdown("""
<style>
    /* Đảm bảo header và nút sidebar rõ ràng trên di động */
    header[data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧭 Điều hướng")
    if st.button("🏠 Về Trang Chủ", use_container_width=True):
        st.switch_page("Dashboard.py")
    st.divider()

# --- AUTHENTICATION CHECK ---
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

user_info = st.session_state.user_info
user_role = user_info.get("role")
user_name = user_info.get("name")
user_dept = user_info.get("department")

# --- ROLE CHECK ---
allowed_roles = ['truong_ca', 'truong_bp', 'qc_manager', 'director', 'bgd_tan_phu', 'admin']
if user_role not in allowed_roles:
    st.error(f"⛔ Role '{user_role}' không có quyền phê duyệt!")
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---

gc = init_gspread()

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

# --- DETERMINE FILTER BASED ON ROLE ---
ROLE_ACTION_STATUSES = {
    'truong_ca': 'cho_truong_ca',
    'truong_bp': 'cho_truong_bp',
    'qc_manager': ['cho_qc_manager', 'xac_nhan_kp_qc_manager'],
    'director': ['cho_giam_doc', 'xac_nhan_kp_director'],
    'bgd_tan_phu': 'cho_bgd_tan_phu'
}

# Admin can act as any role
if user_role == 'admin':
    st.info("🔑 Admin Mode: Chọn role để xem NCR cần phê duyệt")
    selected_role = st.selectbox(
        "Xem với quyền:",
        ['truong_ca', 'truong_bp', 'qc_manager', 'director', 'bgd_tan_phu']
    )
    filter_status = ROLE_ACTION_STATUSES[selected_role]
else:
    selected_role = user_role
    filter_status = ROLE_ACTION_STATUSES.get(user_role)

if not filter_status:
    st.error("Role không hợp lệ!")
    st.stop()

# Determine if we need department filter
needs_dept_filter = selected_role in ['truong_ca', 'truong_bp']

# If user is Admin or has 'all' department access, skip the filter
if user_dept == 'all' or user_role == 'admin':
    filter_department = None
else:
    filter_department = user_dept if needs_dept_filter else None

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    df_original, df_grouped = load_ncr_data_with_grouping(
        gc,
        filter_status=filter_status,
        filter_department=filter_department
    )

# --- DISPLAY STATUS INFO ---
display_status = get_status_display_name(filter_status)
if filter_department:
    st.info(f"Đang hiển thị phiếu trạng thái: **{display_status}** - Bộ phận: **{filter_department.upper()}**")
else:
    st.info(f"Đang hiển thị phiếu trạng thái: **{display_status}**")

if df_grouped.empty:
    st.success("🎉 Không có phiếu nào cần phê duyệt!")
else:
    count = len(df_grouped)
    st.markdown(f"**Tìm thấy {count} phiếu cần xử lý**")
    
    # --- RENDER TICKETS ---
    for _, row in df_grouped.iterrows():
        so_phieu = row['so_phieu']
        trang_thai = row['trang_thai']
        ngay_lap = row['ngay_lap']
        nguoi_lap = row['nguoi_lap_phieu']
        tong_loi = row['sl_loi']
        
        status_name = get_status_display_name(trang_thai)
        expander_label = f"📋 {so_phieu} | {status_name} | 👤 {nguoi_lap} | ⚠️ {tong_loi} lỗi"
        
        with st.expander(expander_label, expanded=False):
            # Info grid
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"📅 **Ngày tạo:** {ngay_lap}")
            with col2:
                if 'bo_phan' in row:
                    st.write(f"🏢 **Bộ phận:** {row['bo_phan'].upper()}")
            
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
                    img_list = str(hinh_anh_val).split('\n')
                    # Filter out empty or 'nan' strings
                    img_list = [url.strip() for url in img_list if url.strip() and url.lower() != 'nan']
                    
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
                        
                        # Add direct links
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
                st.markdown("#### 💡 Chuỗi đề xuất xử lý")
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
                st.markdown("#### ❌ Danh sách lỗi chi tiết")
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
            
            # Logic for NEXT STATUS based on Flow
            next_status = STATUS_FLOW.get(trang_thai, 'hoan_thanh')
            
            # Logic for REJECT STATUS based on Escalation
            reject_status = REJECT_ESCALATION.get(trang_thai, 'draft')
            
            # Special Logic for Corrective Action Acceptance
            is_awaiting_kp_confirm = str(trang_thai).startswith("xac_nhan_kp_")
            
            if is_awaiting_kp_confirm:
                st.markdown("### 🔍 Xác nhận Hành động khắc phục")
                st.write("Người nhận đã gửi phản hồi. Bạn có chấp nhận kết quả này không?")
                if st.button("✅ Chấp nhận & Quay lại xét duyệt", key=f"accept_kp_{so_phieu}", type="primary", use_container_width=True):
                    with st.spinner("Đang xác nhận..."):
                        from utils.ncr_helpers import accept_corrective_action
                        success, message = accept_corrective_action(gc, so_phieu, selected_role)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                st.divider()

            col_approve, col_reject = st.columns(2)
            
            # Additional Action: Assign Corrective Action
            can_assign_kp = (selected_role == 'qc_manager' and trang_thai == 'cho_qc_manager') or \
                           (selected_role == 'director' and trang_thai == 'cho_giam_doc')
            
            if can_assign_kp:
                with st.expander("🛠️ Giao hành động khắc phục (Corrective Action)", expanded=False):
                    assign_to = 'truong_bp'
                    if selected_role == 'director':
                        assign_to = st.radio("Giao cho:", ['truong_bp', 'qc_manager'], horizontal=True, key=f"assign_to_{so_phieu}")
                    
                    kp_msg = st.text_area("Yêu cầu cụ thể:", key=f"kp_msg_{so_phieu}", placeholder="Nhập yêu cầu khắc phục...")
                    kp_deadline = st.date_input("Hạn chót:", key=f"kp_dl_{so_phieu}")
                    
                    if st.button("🚀 Gửi yêu cầu khắc phục", key=f"send_kp_{so_phieu}", use_container_width=True):
                        if not kp_msg.strip():
                            st.error("Vui lòng nhập nội dung yêu cầu!")
                        else:
                            with st.spinner("Đang giao task..."):
                                from utils.ncr_helpers import assign_corrective_action
                                success, message = assign_corrective_action(
                                    gc, so_phieu, selected_role, assign_to, kp_msg, kp_deadline
                                )
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                st.write("")
            
            with col_approve:
                approve_label = "✅ PHÊ DUYỆT" if selected_role != 'bgd_tan_phu' else "✅ HOÀN TẤT PHIẾU"
                if st.button(approve_label, key=f"approve_{so_phieu}", type="primary", use_container_width=True):
                    # Validation cho các role cần nhập solution
                    validation_failed = False
                    
                    if selected_role == 'truong_bp' and (not bp_solution or not bp_solution.strip()):
                        st.error("⚠️ Vui lòng nhập biện pháp xử lý tức thời!")
                        validation_failed = True
                    
                    if selected_role == 'qc_manager' and (not qc_solution or not qc_solution.strip()):
                        st.error("⚠️ Vui lòng nhập hướng giải quyết!")
                        validation_failed = True
                    
                    if selected_role == 'director' and (not director_solution or not director_solution.strip()):
                        st.error("⚠️ Vui lòng nhập hướng xử lý!")
                        validation_failed = True
                    
                    if not validation_failed:
                        with st.spinner("Đang xử lý..."):
                            success, message = update_ncr_status(
                                gc=gc,
                                so_phieu=so_phieu,
                                new_status=next_status,
                                approver_name=user_name,
                                approver_role=selected_role,
                                solution=qc_solution,
                                bp_solution=bp_solution,
                                director_solution=director_solution
                            )
                            
                            if success:
                                st.success(f"✅ {message} -> {get_status_display_name(next_status)}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
            
            with col_reject:
                if st.button(
                    "❌ TỪ CHỐI",
                    key=f"reject_btn_{so_phieu}",
                    use_container_width=True
                ):
                    st.session_state[f'show_reject_{so_phieu}'] = True
            
            # Reject reason input (conditional)
            if st.session_state.get(f'show_reject_{so_phieu}', False):
                reject_reason = st.text_area(
                    "Lý do từ chối (Ghi chú):",
                    key=f"reject_reason_{so_phieu}",
                    placeholder="Nhập lý do..."
                )
                
                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Xác nhận từ chối", key=f"confirm_reject_{so_phieu}", type="secondary"):
                        if not reject_reason or reject_reason.strip() == '':
                            st.warning("Vui lòng nhập lý do từ chối!")
                        else:
                            with st.spinner("Đang xử lý..."):
                                success, message = update_ncr_status(
                                    gc=gc,
                                    so_phieu=so_phieu,
                                    new_status=reject_status, # Escalation status
                                    approver_name=user_name,
                                    approver_role=selected_role,
                                    reject_reason=reject_reason
                                )
                                
                                if success:
                                    st.warning(f"❌ {message} -> {get_status_display_name(reject_status)}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                with col_cancel:
                    if st.button("Hủy", key=f"cancel_reject_{so_phieu}"):
                         st.session_state[f'show_reject_{so_phieu}'] = False
                         st.rerun()
