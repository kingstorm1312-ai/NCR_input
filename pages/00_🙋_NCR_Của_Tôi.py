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
    get_status_display_name,
    get_status_color,
    init_gspread,
    cancel_ncr
)

# --- PAGE SETUP ---
st.set_page_config(page_title="NCR Của Tôi", page_icon="🙋", layout="centered", initial_sidebar_state="auto")

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
user_name = user_info.get("name")
user_role = user_info.get("role")

# --- GOOGLE SHEETS CONNECTION ---

gc = init_gspread()

# --- HEADER ---
st.title("🙋 NCR Của Tôi")
st.caption(f"Xin chào **{user_name}** - Quản lý các phiếu NCR bạn đã tạo")

# Clear cache button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Làm mới", help="Clear cache và tải lại dữ liệu mới nhất"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# --- HELPER: IMAGE POPUP ---
# --- HELPER: RESUBMIT FUNCTION ---
def resubmit_ncr(so_phieu):
    """Gửi lại phiếu NCR (reset status về cho_truong_ca)"""
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        all_data = ws.get_all_values()
        headers = all_data[0]
        
        # Map column names
        from utils.ncr_helpers import COLUMN_MAPPING
        col_so_phieu = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
        col_trang_thai = headers.index(COLUMN_MAPPING.get('trang_thai', 'trang_thai'))
        col_thoi_gian = headers.index(COLUMN_MAPPING.get('thoi_gian_cap_nhat', 'thoi_gian_cap_nhat'))
        
        # Find rows to update
        rows_to_update = []
        for idx, row in enumerate(all_data[1:], start=2):
            if row[col_so_phieu] == so_phieu:
                rows_to_update.append(idx)
        
        if not rows_to_update:
            return False, "Không tìm thấy phiếu"
        
        # Update status and timestamp
        current_time = get_now_vn_str()
        updates = []
        
        for row_idx in rows_to_update:
            updates.append({
                'range': f'{chr(65 + col_trang_thai)}{row_idx}',
                'values': [['cho_truong_ca']]
            })
            updates.append({
                'range': f'{chr(65 + col_thoi_gian)}{row_idx}',
                'values': [[current_time]]
            })
        
        ws.batch_update(updates)
        return True, f"Đã gửi lại phiếu {so_phieu} ({len(rows_to_update)} dòng)"
        
    except Exception as e:
        return False, f"Lỗi: {str(e)}"

# --- LOAD DATA ---
with st.spinner("Đang tải dữ liệu..."):
    # Load all NCR data (no status filter)
    df_all, _ = load_ncr_data_with_grouping(filter_status=None, filter_department=None)

# --- ADMIN VIEW OPTIONS ---
current_view_user = user_name
if user_role == 'admin':
    st.info("🔑 **Admin Mode**: Bạn có thể xem phiếu của chính mình hoặc người khác.")
    all_creators = sorted(df_all['nguoi_lap_phieu'].unique()) if not df_all.empty else []
    view_option = st.selectbox(
        "Chọn người lập phiếu để xem:",
        ["Tất cả người dùng", f"Của tôi ({user_name})"] + [u for u in all_creators if u != user_name]
    )
    
    if view_option == "Tất cả người dùng":
        current_view_user = "all"
    elif view_option.startswith("Của tôi"):
        current_view_user = user_name
    else:
        current_view_user = view_option

# Filter by creator or assigned role
if not df_all.empty:
    if current_view_user == "all":
        df_my_ncrs = df_all.copy()
    else:
        df_my_ncrs = df_all[df_all['nguoi_lap_phieu'] == current_view_user].copy()
    
    # Danh sách task được giao cho role hiện tại (Admin xem hết task KP nếu view "all")
    if user_role == 'admin' and current_view_user == "all":
        df_my_tasks = df_all[df_all['kp_status'] == 'active'].copy()
    else:
        df_my_tasks = df_all[
            (df_all['kp_assigned_to'] == user_role) & 
            (df_all['kp_status'] == 'active')
        ].copy()
else:
    df_my_ncrs = pd.DataFrame()
    df_my_tasks = pd.DataFrame()

# --- STATISTICS ---
if not df_my_ncrs.empty:
    total_tickets = df_my_ncrs['so_phieu'].nunique()
    total_errors = df_my_ncrs['sl_loi'].sum()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📋 Tổng số phiếu", total_tickets)
    with col2:
        draft_count = df_my_ncrs[df_my_ncrs['trang_thai'] == 'draft']['so_phieu'].nunique()
        st.metric("🔴 Cần xử lý", draft_count)
else:
    if current_view_user == "all":
        st.info("ℹ️ Hiện không có phiếu NCR nào trên hệ thống.")
    else:
        st.info(f"ℹ️ User **{current_view_user}** chưa có phiếu NCR nào.")
    st.stop()

st.divider()

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🔴 Cần xử lý", "⏳ Đang chờ duyệt", "🛠️ Hành động khắc phục", "✅ Hoàn thành"])

# --- TAB 1: DRAFT/REJECTED ---
with tab1:
    st.subheader("📋 Phiếu cần xử lý (Draft)")
    
    df_draft = df_my_ncrs[df_my_ncrs['trang_thai'] == 'draft']
    
    if df_draft.empty:
        st.success("✅ Không có phiếu nào cần xử lý!")
    else:
        # Group by ticket
        tickets_draft = df_draft.groupby('so_phieu').agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'ly_do_tu_choi': 'first',
            'trang_thai': 'first'
        }).reset_index()
        
        for _, ticket in tickets_draft.iterrows():
            so_phieu = ticket['so_phieu']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            ly_do = ticket['ly_do_tu_choi']
            
            with st.container(border=True):
                # Header
                col_title, col_badge = st.columns([3, 1])
                with col_title:
                    st.markdown(f"### 📋 {so_phieu}")
                with col_badge:
                    st.markdown(":red[DRAFT]")
                
                # Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                with col2:
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                
                # Rejection reason (if exists)
                if ly_do and str(ly_do).strip():
                    # Format is now usually: "[Approver Name (ROLE)] Reason"
                    st.error(f"❌ **Lý do từ chối:** {ly_do}")
                    
                    # Highlight if rejected by high level based on ROLE in string
                    lower_reason = str(ly_do).lower()
                    if '(qc_manager)' in lower_reason or '(qc manager)' in lower_reason:
                         st.warning("⚠️ **Lưu ý:** Phiếu bị từ chối bởi QC Manager!")
                    elif '(director)' in lower_reason or '(giam_doc)' in lower_reason:
                         st.warning("⚠️ **Lưu ý:** Phiếu bị từ chối bởi Giám Đốc!")
                    elif '(bgd_tan_phu)' in lower_reason:
                         st.warning("⚠️ **Lưu ý:** Phiếu bị từ chối bởi BGĐ Tân Phú!")
                
                # Error details
                with st.expander("🔍 Chi tiết lỗi"):
                    ticket_rows = df_draft[df_draft['so_phieu'] == so_phieu]
                    if not ticket_rows.empty:
                        display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'don_vi_tinh', 'muc_do']
                        column_config = {
                            "ten_loi": "Tên lỗi",
                            "vi_tri_loi": "Vị trí",
                            "sl_loi": "SL",
                            "don_vi_tinh": "ĐVT",
                            "muc_do": "Mức độ"
                        }
                        available_cols = [col for col in display_cols if col in ticket_rows.columns]
                        st.dataframe(
                            ticket_rows[available_cols].rename(columns=column_config),
                            use_container_width=True,
                            hide_index=True
                        )
                
                
                # --- STATE MANAGEMENT ---
                edit_key = f"edit_mode_{so_phieu}"
                if edit_key not in st.session_state:
                    st.session_state[edit_key] = False

                # --- ACTIONS ---
                col_edit_btn, col_resubmit_btn, col_cancel_btn = st.columns([1, 1, 1])
                
                with col_edit_btn: # Action: Edit
                    # Toggle Edit Mode Button
                    btn_label = "✏️ Chỉnh sửa" if not st.session_state[edit_key] else "❌ Hủy sửa"
                    if st.button(btn_label, key=f"edit_btn_{so_phieu}", use_container_width=True):
                        st.session_state[edit_key] = not st.session_state[edit_key]
                        st.rerun()
                
                with col_resubmit_btn:
                    if st.button("🚀 Gửi lại ngay", key=f"resubmit_{so_phieu}", type="primary", use_container_width=True):
                        if resubmit_ncr(so_phieu):
                            st.success(f"Đã gửi lại phiếu {so_phieu}!")
                            st.rerun()
                        else:
                            st.error("Lỗi khi gửi lại phiếu.")
                            
                with col_cancel_btn:
                    if st.button("🗑️ HỦY PHIẾU", key=f"cancel_btn_{so_phieu}", type="secondary", use_container_width=True):
                        st.session_state[f"show_cancel_confirm_{so_phieu}"] = True
                
                # Cancel Confirmation
                if st.session_state.get(f"show_cancel_confirm_{so_phieu}", False):
                    st.warning("⚠️ **Bạn có chắc muốn hủy phiếu này không?** Hành động này không thể hoàn tác.")
                    cancel_reason = st.text_input("Lý do hủy:", key=f"cancel_reason_{so_phieu}")
                    
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("✅ Xác nhận Hủy", key=f"confirm_cancel_{so_phieu}"):
                            if not cancel_reason.strip():
                                st.error("Vui lòng nhập lý do hủy!")
                            else:
                                if cancel_ncr(gc, so_phieu, cancel_reason):
                                    st.success("Đã hủy phiếu thành công!")
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error("Lỗi khi hủy phiếu.")
                    with c_no:
                        if st.button("❌ Bỏ qua", key=f"ignore_cancel_{so_phieu}"):
                            st.session_state[f"show_cancel_confirm_{so_phieu}"] = False
                            st.rerun()
                
                # Edit form (when edit mode is ON)
                if st.session_state[edit_key]:
                    st.write("---")
                    st.markdown("### ✏️ Chỉnh sửa phiếu")
                    
                    ticket_rows = df_draft[df_draft['so_phieu'] == so_phieu].copy()
                    
                    # Calculate row indices in sheet
                    try:
                        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                        ws = sh.worksheet("NCR_DATA")
                        all_data = ws.get_all_values()
                        headers = all_data[0]
                        
                        from utils.ncr_helpers import COLUMN_MAPPING, upload_images_to_cloud
                        col_so_phieu_idx = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
                        col_sl_loi_idx = headers.index(COLUMN_MAPPING.get('sl_loi', 'so_luong_loi'))
                        col_ten_loi_idx = headers.index(COLUMN_MAPPING.get('ten_loi', 'ten_loi'))
                        col_hinh_anh_idx = headers.index(COLUMN_MAPPING.get('hinh_anh', 'hinh_anh'))
                        
                        # Find rows for this ticket
                        error_rows = []
                        current_images_str = ""
                        
                        for idx, row in enumerate(all_data[1:], start=2):
                            if row[col_so_phieu_idx] == so_phieu:
                                error_rows.append({
                                    'sheet_row': idx,
                                    'ten_loi': row[col_ten_loi_idx],
                                    'sl_loi': row[col_sl_loi_idx]
                                })
                                # Get images from the first row found (assuming all rows of a ticket share same images)
                                if not current_images_str:
                                    current_images_str = row[col_hinh_anh_idx]
                        
                        # --- 1. EDIT ERRORS ---
                        st.markdown("**1. Sửa lỗi hiện có:**")
                        updated_errors = []
                        deleted_rows = []
                        
                        for i, err in enumerate(error_rows):
                            col1, col2, col3 = st.columns([3, 2, 1])
                            with col1:
                                st.text(err['ten_loi'])
                            with col2:
                                new_qty = st.number_input(
                                    "SL",
                                    min_value=0.0,
                                    step=0.1,
                                    format="%.1f",
                                    value=float(err['sl_loi']) if err['sl_loi'] else 0.0,
                                    key=f"edit_qty_{so_phieu}_{i}",
                                    label_visibility="collapsed"
                                )
                            with col3:
                                if st.button("🗑️", key=f"del_{so_phieu}_{i}", help="Xóa lỗi này"):
                                    deleted_rows.append(err['sheet_row'])
                            
                            if err['sheet_row'] not in deleted_rows:
                                updated_errors.append({
                                    'sheet_row': err['sheet_row'],
                                    'sl_loi': new_qty
                                })
                        
                        # --- 2. EDIT IMAGES ---
                        st.write("")
                        st.markdown("**2. Chỉnh sửa hình ảnh:**")
                        
                        # Parse existing images
                        current_images = []
                        if current_images_str:
                            current_images = [url.strip() for url in current_images_str.split('\n') if url.strip()]
                        
                        # Display existing images for deletion
                        images_to_keep = []
                        if current_images:
                            st.caption("Ảnh hiện tại (Chọn để xóa):")
                            cols_img = st.columns(3)
                            for i, img_url in enumerate(current_images):
                                with cols_img[i % 3]:
                                    st.image(img_url, use_container_width=True)
                                    # Checkbox to mark for deletion (Default: False = Keep)
                                    if not st.checkbox(f"Xóa ảnh {i+1}", key=f"del_img_{so_phieu}_{i}"):
                                        images_to_keep.append(img_url)
                        else:
                            st.info("Chưa có hình ảnh nào.")
                            
                        # Add new images
                        st.caption("Thêm ảnh mới:")
                        new_images_files = st.file_uploader(
                            "Tải lên ảnh bổ sung",
                            type=['png', 'jpg', 'jpeg'],
                            accept_multiple_files=True,
                            key=f"add_img_{so_phieu}"
                        )
                        
                        # --- SAVE BUTTON ---
                        st.write("---")
                        if st.button(
                            "💾 LƯU THAY ĐỔI",
                            key=f"save_edit_{so_phieu}",
                            type="primary",
                            use_container_width=True
                        ):
                            try:
                                with st.spinner("Đang lưu thay đổi..."):
                                    updates = []
                                    
                                    # 1. Handle Images
                                    final_image_list = images_to_keep.copy()
                                    
                                    # Upload new images
                                    if new_images_files:
                                        new_urls_str = upload_images_to_cloud(new_images_files, so_phieu)
                                        if new_urls_str:
                                            final_image_list.extend(new_urls_str.split('\n'))
                                    
                                    final_images_str = "\n".join(final_image_list)
                                    
                                    # Update 'hinh_anh' column for ALL rows of this ticket
                                    # (Since all rows share same header info)
                                    all_ticket_rows = [r['sheet_row'] for r in error_rows]
                                    for r_idx in all_ticket_rows:
                                         if r_idx not in deleted_rows: # Only update non-deleted rows
                                            # Fix: Use rowcol_to_a1 for columns > Z
                                            cell_range = gspread.utils.rowcol_to_a1(r_idx, col_hinh_anh_idx + 1)
                                            updates.append({
                                                'range': cell_range,
                                                'values': [[final_images_str]]
                                            })

                                    # 2. Update Quantities
                                    for upd in updated_errors:
                                        cell_range = gspread.utils.rowcol_to_a1(upd["sheet_row"], col_sl_loi_idx + 1)
                                        updates.append({
                                            'range': cell_range,
                                            'values': [[str(upd['sl_loi'])]]
                                        })
                                    
                                    # 3. Delete Rows
                                    for del_row in deleted_rows:
                                        # Mark as deleted
                                        range_so_phieu = gspread.utils.rowcol_to_a1(del_row, col_so_phieu_idx + 1)
                                        updates.append({
                                            'range': range_so_phieu,
                                            'values': [[f"{so_phieu}_DELETED"]] 
                                        })
                                        # Also zero out quantity
                                        range_sl = gspread.utils.rowcol_to_a1(del_row, col_sl_loi_idx + 1)
                                        updates.append({
                                            'range': range_sl,
                                            'values': [['0']]
                                        })
                                    
                                    if updates:
                                        ws.batch_update(updates)
                                        st.success("✅ Đã lưu thay đổi!")
                                        st.session_state[edit_key] = False
                                        st.rerun()
                                    else:
                                        st.info("Không có thay đổi nào")
                                    
                            except Exception as e:
                                st.error(f"Lỗi khi lưu: {str(e)}")
                    
                    except Exception as e:
                        st.error(f"Lỗi khi load dữ liệu edit: {str(e)}")
                
                # End of loop logic

# --- TAB 2: PENDING APPROVAL ---
with tab2:
    st.subheader("⏳ Phiếu đang chờ duyệt")
    
    pending_statuses = ['cho_truong_ca', 'cho_truong_bp', 'cho_qc_manager', 'cho_giam_doc']
    df_pending = df_my_ncrs[df_my_ncrs['trang_thai'].isin(pending_statuses)]
    
    if df_pending.empty:
        st.info("ℹ️ Không có phiếu nào đang chờ duyệt")
    else:
        # Group by ticket
        tickets_pending = df_pending.groupby(['so_phieu', 'trang_thai']).agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'thoi_gian_cap_nhat': 'first'
        }).reset_index()
        
        for _, ticket in tickets_pending.iterrows():
            so_phieu = ticket['so_phieu']
            status = ticket['trang_thai']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            last_update = ticket.get('thoi_gian_cap_nhat', '')
            
            with st.container(border=True):
                # Header
                col_title, col_badge = st.columns([3, 1])
                with col_title:
                    st.markdown(f"### 📋 {so_phieu}")
                with col_badge:
                    status_color = get_status_color(status)
                    st.markdown(f":{status_color}[{get_status_display_name(status)}]")
                
                # Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                with col2:
                    if last_update:
                        st.write(f"🕐 **Cập nhật:** {last_update}")
                
                # Error details
                with st.expander("🔍 Chi tiết lỗi"):
                    ticket_rows = df_pending[df_pending['so_phieu'] == so_phieu]
                    if not ticket_rows.empty:
                        display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'don_vi_tinh', 'muc_do']
                        column_config = {
                            "ten_loi": "Tên lỗi",
                            "vi_tri_loi": "Vị trí",
                            "sl_loi": "SL",
                            "don_vi_tinh": "ĐVT",
                            "muc_do": "Mức độ"
                        }
                        available_cols = [col for col in display_cols if col in ticket_rows.columns]
                        st.dataframe(
                            ticket_rows[available_cols].rename(columns=column_config),
                            use_container_width=True,
                            hide_index=True
                        )

                # --- EDIT FUNCTIONALITY (Only for 'cho_truong_ca') ---
                if status == 'cho_truong_ca':
                    edit_key = f"edit_pending_{so_phieu}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False
                    
                    # Toggle edit mode
                    st.write("")
                    if st.button(
                        "✏️ SỬA PHIẾU" if not st.session_state[edit_key] else "❌ HỦY SỬA",
                        key=f"toggle_edit_pending_{so_phieu}",
                        use_container_width=True
                    ):
                        st.session_state[edit_key] = not st.session_state[edit_key]
                        st.rerun()
                    
                    # Edit form (when edit mode is ON)
                    if st.session_state[edit_key]:
                        st.write("---")
                        st.markdown("### ✏️ Chỉnh sửa phiếu (Đang chờ duyệt)")
                        
                        # Calculate row indices in sheet
                        try:
                            sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                            ws = sh.worksheet("NCR_DATA")
                            all_data = ws.get_all_values()
                            headers = all_data[0]
                            
                            from utils.ncr_helpers import COLUMN_MAPPING
                            col_so_phieu_idx = headers.index(COLUMN_MAPPING.get('so_phieu', 'so_phieu_ncr'))
                            col_sl_loi_idx = headers.index(COLUMN_MAPPING.get('sl_loi', 'so_luong_loi'))
                            col_ten_loi_idx = headers.index(COLUMN_MAPPING.get('ten_loi', 'ten_loi'))
                            
                            # Find rows for this ticket
                            error_rows = []
                            for idx, row in enumerate(all_data[1:], start=2):
                                if row[col_so_phieu_idx] == so_phieu:
                                    error_rows.append({
                                        'sheet_row': idx,
                                        'ten_loi': row[col_ten_loi_idx],
                                        'sl_loi': row[col_sl_loi_idx]
                                    })
                            
                            # Edit existing errors
                            updated_errors = []
                            deleted_rows = []
                            
                            for i, err in enumerate(error_rows):
                                col1, col2, col3 = st.columns([3, 2, 1])
                                with col1:
                                    st.text(err['ten_loi'])
                                with col2:
                                    new_qty = st.number_input(
                                        "SL",
                                        min_value=0.0,
                                        step=0.1,
                                        format="%.1f",
                                        value=float(err['sl_loi']) if err['sl_loi'] else 0.0,
                                        key=f"edit_qty_pending_{so_phieu}_{i}",
                                        label_visibility="collapsed"
                                    )
                                with col3:
                                    if st.button("🗑️", key=f"del_pending_{so_phieu}_{i}", help="Xóa lỗi này"):
                                        deleted_rows.append(err['sheet_row'])
                                
                                if err['sheet_row'] not in deleted_rows:
                                    updated_errors.append({
                                        'sheet_row': err['sheet_row'],
                                        'sl_loi': new_qty
                                    })
                            
                            # Save changes button
                            st.write("")
                            if st.button(
                                "💾 LƯU THAY ĐỔI",
                                key=f"save_edit_pending_{so_phieu}",
                                type="primary",
                                use_container_width=True
                            ):
                                updates = []
                                
                                # Update quantities
                                for upd in updated_errors:
                                    updates.append({
                                        'range': f'{chr(65 + col_sl_loi_idx)}{upd["sheet_row"]}',
                                        'values': [[str(upd['sl_loi'])]]
                                    })
                                
                                # Delete rows (update sl to 0)
                                for del_row in deleted_rows:
                                    updates.append({
                                        'range': f'{chr(65 + col_sl_loi_idx)}{del_row}',
                                        'values': [['0']]
                                    })
                                
                                if updates:
                                    ws.batch_update(updates)
                                    st.success("✅ Đã lưu thay đổi!")
                                    st.session_state[edit_key] = False
                                    st.rerun()
                                else:
                                    st.info("Không có thay đổi nào")
                                    
                        except Exception as e:
                            st.error(f"Lỗi khi tải/lưu dữ liệu: {str(e)}")

# --- TAB 3: CORRECTIVE ACTIONS (TASKS) ---
with tab3:
    st.subheader("🛠️ Hành động khắc phục (Task được giao)")
    
    if df_my_tasks.empty:
        st.success("🎉 Bạn không có hành động khắc phục nào cần xử lý!")
    else:
        st.info(f"Bạn có {len(df_my_tasks)} yêu cầu khắc phục cần phản hồi.")
        
        for _, task in df_my_tasks.iterrows():
            so_phieu = task['so_phieu']
            msg = task['kp_message']
            deadline = task['kp_deadline']
            by_role = task.get('kp_assigned_by', '').upper()
            
            with st.container(border=True):
                st.markdown(f"### 📋 {so_phieu}")
                st.warning(f"**Yêu cầu từ {by_role}:**\n{msg}")
                st.markdown(f"📅 **Hạn chót:** :red[**{deadline}**]")
                
                # --- CHI TIẾT PHIẾU (Full Info like Approval Page) ---
                with st.expander("🔍 Xem chi tiết phiếu & Hình ảnh", expanded=False):
                    # --- HÌNH ẢNH ---
                    st.markdown("#### 📷 Hình ảnh minh họa")
                    hinh_anh_val = task.get('hinh_anh', "")
                    if pd.notna(hinh_anh_val) and str(hinh_anh_val).strip():
                        img_list = str(hinh_anh_val).split('\n')
                        img_list = [url.strip() for url in img_list if url.strip() and url.lower() != 'nan']
                        
                        if img_list:
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
                        st.write(f"📁 **Hợp đồng:** {task.get('hop_dong', 'N/A')}")
                        st.write(f"🔢 **Mã vật tư:** {task.get('ma_vat_tu', 'N/A')}")
                        st.write(f"📦 **Tên sản phẩm:** {task.get('ten_sp', 'N/A')}")
                        st.write(f"🏷️ **Phân loại:** {task.get('phan_loai', 'N/A')}")
                    with ca2:
                        st.write(f"🏢 **Nguồn gốc/NCC:** {task.get('nguon_goc', 'N/A')}")
                        st.write(f"🔢 **SL Kiểm:** {task.get('sl_kiem', 0)}")
                        st.write(f"📦 **SL Lô:** {task.get('sl_lo_hang', 0)}")
                        st.write(f"🕒 **Cập nhật cuối:** {task.get('thoi_gian_cap_nhat', 'N/A')}")
                    
                    if task.get('mo_ta_loi'):
                        st.markdown(f"📝 **Mô tả lỗi / Quy cách:**\n{task.get('mo_ta_loi')}")
                    
                    st.markdown("---")
                    
                    # --- TIMELINE ĐỀ XUẤT GIẢI PHÁP ---
                    st.markdown("#### 💡 Chuỗi đề xuất xử lý")
                    has_any_sol = False
                    if task.get('bien_phap_truong_bp'):
                        has_any_sol = True
                        st.info(f"**👔 Trưởng BP - Biện pháp xử lý tức thời:**\n{task['bien_phap_truong_bp']}")
                    if task.get('huong_giai_quyet'):
                        has_any_sol = True
                        st.success(f"**🔬 QC Manager - Hướng giải quyết:**\n{task['huong_giai_quyet']}")
                    if task.get('huong_xu_ly_gd'):
                        has_any_sol = True
                        st.warning(f"**👨‍💼 Giám đốc - Hướng xử lý:**\n{task['huong_xu_ly_gd']}")
                    if not has_any_sol:
                        st.caption("_Chưa có đề xuất xử lý từ các cấp quản lý._")

                    st.markdown("---")
                    st.markdown("#### ❌ Danh sách lỗi chi tiết")
                    tk_rows = df_all[df_all['so_phieu'] == so_phieu]
                    if not tk_rows.empty:
                        display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'don_vi_tinh', 'muc_do']
                        column_config = {
                            "ten_loi": "Tên lỗi",
                            "vi_tri_loi": "Vị trí",
                            "sl_loi": "SL",
                            "don_vi_tinh": "ĐVT",
                            "muc_do": "Mức độ"
                        }
                        avail_cols = [col for col in display_cols if col in tk_rows.columns]
                        st.dataframe(
                            tk_rows[avail_cols].rename(columns=column_config), 
                            use_container_width=True, 
                            hide_index=True
                        )
                
                # Deadline warning
                try:
                    deadline_dt = pd.to_datetime(deadline).date()
                    today = datetime.now().date()
                    if today > deadline_dt:
                        st.error(f"⚠️ QUÁ HẠN: Task này đã trễ hạn { (today - deadline_dt).days } ngày!")
                except:
                    pass
                
                # Form to respond
                with st.expander("📝 Phản hồi khắc phục", expanded=True):
                    response = st.text_area("Nội dung phản hồi:", key=f"res_msg_{so_phieu}", placeholder="Nhập kết quả xử lý...")
                    if st.button("✅ Gửi hoàn thành", key=f"send_res_{so_phieu}", use_container_width=True):
                        if not response.strip():
                            st.error("Vui lòng nhập nội dung phản hồi!")
                        else:
                            with st.spinner("Đang gửi..."):
                                from utils.ncr_helpers import complete_corrective_action
                                success, message = complete_corrective_action(gc, so_phieu, response)
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)

# --- TAB 4: COMPLETED ---
with tab4:
    st.subheader("✅ Phiếu đã hoàn thành")
    
    df_completed = df_my_ncrs[df_my_ncrs['trang_thai'] == 'hoan_thanh']
    
    if df_completed.empty:
        st.info("ℹ️ Chưa có phiếu nào hoàn thành")
    else:
        # Group by ticket
        tickets_completed = df_completed.groupby('so_phieu').agg({
            'ngay_lap': 'first',
            'sl_loi': 'sum',
            'ten_loi': lambda x: ', '.join(x.unique()),
            'thoi_gian_cap_nhat': 'first'
        }).reset_index()
        
        st.success(f"🎉 Đã hoàn thành {len(tickets_completed)} phiếu!")
        
        for _, ticket in tickets_completed.iterrows():
            so_phieu = ticket['so_phieu']
            ngay_lap = ticket['ngay_lap']
            tong_loi = ticket['sl_loi']
            
            with st.expander(f"📋 {so_phieu} - {int(tong_loi)} lỗi"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📅 **Ngày tạo:** {ngay_lap}")
                with col2:
                    st.write(f"⚠️ **Tổng lỗi:** {int(tong_loi)}")
                
                # Error details
                ticket_rows = df_completed[df_completed['so_phieu'] == so_phieu]
                if not ticket_rows.empty:
                    display_cols = ['ten_loi', 'vi_tri_loi', 'sl_loi', 'don_vi_tinh', 'muc_do']
                    column_config = {
                        "ten_loi": "Tên lỗi",
                        "vi_tri_loi": "Vị trí",
                        "sl_loi": "SL",
                        "don_vi_tinh": "ĐVT",
                        "muc_do": "Mức độ"
                    }
                    available_cols = [col for col in display_cols if col in ticket_rows.columns]
                    st.dataframe(
                        ticket_rows[available_cols].rename(columns=column_config),
                        use_container_width=True,
                        hide_index=True
                    )
                
                # --- EXPORT BUTTONS ---
                st.write("")
                st.markdown("##### 🖨️ Xuất báo cáo:")
                
                # Layout export buttons
                xc1, xc2 = st.columns(2)
                
                # --- EXPORT BBK ---
                with xc1:
                    if st.button(f"📄 Xuất BBK (PDF)", key=f"exp_bbk_{so_phieu}"):
                        with st.spinner("Đang tạo file BBK..."):
                            try:
                                # Prepare data
                                from utils.export_helper import generate_ncr_pdf
                                
                                # Lấy thông tin chung (dòng đầu tiên)
                                ticket_info = ticket_rows.iloc[0].to_dict()
                                # Lấy bảng lỗi
                                df_errs = ticket_rows
                                
                                # Template Path
                                template_path = r"D:\Thành\Work\Antigravity\NCR_mobile_project\Template\Template BBK FI.docx"
                                
                                pdf_path, docx_path = generate_ncr_pdf(template_path, ticket_info, df_errs, f"BBK_{so_phieu}")
                                
                                if pdf_path and os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as f:
                                        st.download_button(
                                            label=f"⬇️ Tải BBK PDF",
                                            data=f,
                                            file_name=os.path.basename(pdf_path),
                                            mime="application/pdf",
                                            key=f"dl_bbk_pdf_{so_phieu}"
                                        )
                                elif docx_path and os.path.exists(docx_path):
                                     st.warning("Không thể tạo PDF (do thiếu MS Word?), vui lòng tải file Word.")
                                     with open(docx_path, "rb") as f:
                                        st.download_button(
                                            label=f"⬇️ Tải BBK Word",
                                            data=f,
                                            file_name=os.path.basename(docx_path),
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key=f"dl_bbk_docx_{so_phieu}"
                                        )
                            except Exception as e:
                                st.error(f"Lỗi xuất file: {str(e)}")

                # --- EXPORT NCR ---
                with xc2:
                    if st.button(f"📄 Xuất NCR (PDF)", key=f"exp_ncr_{so_phieu}"):
                        with st.spinner("Đang tạo file NCR..."):
                            try:
                                # Prepare data
                                from utils.export_helper import generate_ncr_pdf
                                ticket_info = ticket_rows.iloc[0].to_dict()
                                df_errs = ticket_rows
                                
                                # Template Path
                                template_path = r"D:\Thành\Work\Antigravity\NCR_mobile_project\Template\Template NCR FI.docx"
                                
                                pdf_path, docx_path = generate_ncr_pdf(template_path, ticket_info, df_errs, f"NCR_{so_phieu}")
                                
                                if pdf_path and os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as f:
                                        st.download_button(
                                            label=f"⬇️ Tải NCR PDF",
                                            data=f,
                                            file_name=os.path.basename(pdf_path),
                                            mime="application/pdf",
                                            key=f"dl_ncr_pdf_{so_phieu}"
                                        )
                                elif docx_path and os.path.exists(docx_path):
                                     st.warning("Không thể tạo PDF (do thiếu MS Word?), vui lòng tải file Word.")
                                     with open(docx_path, "rb") as f:
                                        st.download_button(
                                            label=f"⬇️ Tải NCR Word",
                                            data=f,
                                            file_name=os.path.basename(docx_path),
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key=f"dl_ncr_docx_{so_phieu}"
                                        )
                            except Exception as e:
                                st.error(f"Lỗi xuất file: {str(e)}")

# --- FOOTER ---
st.divider()
if st.button("🔙 Quay lại Dashboard"):
    st.switch_page("Dashboard.py")
