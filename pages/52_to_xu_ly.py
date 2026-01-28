import streamlit as st
import pandas as pd
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.auth import require_roles
from core.services import dnxl_service
from utils.ncr_helpers import upload_images_to_cloud

# --- PAGE SETUP ---
st.set_page_config(page_title="Tổ Xử Lý - DNXL", page_icon="🛠️", layout="centered", initial_sidebar_state="auto")

# --- AUTH ---
user_info = require_roles(['to_xu_ly', 'admin']) # Allow admin to test
user_name = user_info.get("name", "Worker")

st.title("🛠️ Tổ Xử Lý - Danh Sách Việc")
st.caption(f"User: **{user_name}**")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📥 Chờ Nhận", "🔨 Đang Làm / Sửa Lại", "✅ Lịch Sử Đã Gửi"])

# Load Data
with st.spinner("Đang tải dữ liệu..."):
    df_all = dnxl_service.get_pending_dnxl('to_xu_ly', user_name)
    # Optimization: Batch fetch details
    all_details_map = dnxl_service.get_all_dnxl_details_map()

# --- TAB 1: CHỜ NHẬN (MOI_TAO) ---
with tab1:
    df_new = df_all[df_all['status'] == 'moi_tao'] if not df_all.empty else pd.DataFrame()
    
    if df_new.empty:
        st.info("Không có phiếu nào mới cần nhận.")
    else:
        st.success(f"Tìm thấy {len(df_new)} phiếu mới.")
        for _, row in df_new.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**{row['dnxl_id']}** | NCR: {row['ncr_id']}")
                    st.write(f"📅 Deadline: **{row['deadline']}**")
                    st.info(f"🎯 Phạm vi: {row['target_scope']}")
                with c2:
                    if st.button("✋ NHẬN VIỆC", key=f"claim_{row['dnxl_id']}", type="primary"):
                        suc, msg = dnxl_service.claim_dnxl(row['dnxl_id'], user_name)
                        if suc:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                
                with st.expander("Xem yêu cầu chi tiết"):
                    st.write(f"📝 **Hướng dẫn:** {row['handling_instruction']}")
                    # Show details readonly from MAP
                    details = all_details_map.get(str(row['dnxl_id']), pd.DataFrame())
                    if not details.empty:
                        st.dataframe(details[['defect_name', 'qty_assigned']], hide_index=True)

# --- TAB 2: ĐANG LÀM (DANG_XU_LY, TRA_LAI) ---
with tab2:
    processing_statuses = ['dang_xu_ly', 'tra_lai']
    df_proc = df_all[df_all['status'].isin(processing_statuses)] if not df_all.empty else pd.DataFrame()
    
    if df_proc.empty:
        st.info("Bạn chưa nhận phiếu nào, hoặc đã hoàn thành hết.")
    else:
        st.markdown(f"Đang có **{len(df_proc)}** phiếu cần xử lý.")
        
        for _, row in df_proc.iterrows():
            status_label = "ĐANG XỬ LÝ" if row['status'] == 'dang_xu_ly' else "BỊ TRẢ LẠI"
            color = "blue" if row['status'] == 'dang_xu_ly' else "red"
            
            with st.expander(f"🔨 {row['dnxl_id']} | :{color}[{status_label}] | Deadline: {row['deadline']}", expanded=True):
                # Header Info
                st.write(f"📦 NCR Gốc: **{row['ncr_id']}**")
                st.write(f"📝 Hướng dẫn: {row['handling_instruction']}")
                
                if row['status'] == 'tra_lai':
                    st.error(f"❌ Lý do trả lại: {row.get('qc_review_note', '')}")
                    
                st.markdown("---")
                
                # Fetch Current Details from MAP
                details = all_details_map.get(str(row['dnxl_id']), pd.DataFrame())
                
                # --- EDITABLE FORM ---
                with st.form(key=f"form_work_{row['dnxl_id']}"):
                    st.markdown("##### 1. Cập nhật kết quả sửa lỗi")
                    
                    # Convert to editable format
                    # We need to preserve list to iterate and create inputs
                    updated_data = []
                    
                    if not details.empty:
                        for i, d_row in details.iterrows():
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                            with c1:
                                st.write(f"**{d_row['defect_name']}**")
                                st.caption(f"Giao: {d_row['qty_assigned']}")
                            with c2:
                                q_fix = st.number_input("Đã sửa", min_value=0.0, step=1.0, value=float(d_row.get('qty_fixed', 0)), key=f"q_{row['dnxl_id']}_{i}")
                            with c3:
                                q_fail = st.number_input("Hỏng", min_value=0.0, step=1.0, value=float(d_row.get('qty_fail', 0)), key=f"f_{row['dnxl_id']}_{i}")
                            with c4:
                                note = st.text_input("Ghi chú", value=str(d_row.get('worker_note', '')), key=f"n_{row['dnxl_id']}_{i}")
                            
                            updated_data.append({
                                'detail_id': d_row['detail_id'],
                                'qty_fixed': q_fix,
                                'qty_fail': q_fail,
                                'worker_note': note
                            })
                            st.divider()
                    else:
                        st.warning("Không tìm thấy chi tiết lỗi.")

                    # Add New Defect Section (Optional)
                    st.markdown("##### 2. Phát sinh thêm lỗi (Nếu có)")
                    new_defect_name = st.text_input("Tên lỗi mới (nếu có)", key=f"new_def_{row['dnxl_id']}")
                    c_n1, c_n2 = st.columns(2)
                    with c_n1:
                        new_qty_fix = st.number_input("SL Sửa (Lỗi mới)", min_value=0.0, key=f"new_q_{row['dnxl_id']}")
                    with c_n2:
                         new_note = st.text_input("Ghi chú (Lỗi mới)", key=f"new_n_{row['dnxl_id']}")
                    
                    st.markdown("##### 3. Thông tin chung & Ảnh")
                    worker_response = st.text_area("Phản hồi chung", value=row.get('worker_response', ''), key=f"resp_{row['dnxl_id']}")
                    
                    # Image Upload
                    new_imgs = st.file_uploader("📸 Tải ảnh báo cáo", accept_multiple_files=True, key=f"img_{row['dnxl_id']}")
                    current_imgs = row.get('worker_images', '')
                    
                    submit_btn = st.form_submit_button("🚀 GỬI KẾT QUẢ")
                    
                    if submit_btn:
                        final_details = updated_data
                        
                        # Add new defect if entered
                        if new_defect_name.strip():
                            final_details.append({
                                'is_new': True,
                                'defect_name': new_defect_name,
                                'qty_fixed': new_qty_fix,
                                'qty_fail': 0,
                                'worker_note': new_note
                            })
                            
                        # Upload Images
                        final_img_str = current_imgs
                        if new_imgs:
                            with st.spinner("Đang upload ảnh..."):
                                uploaded = upload_images_to_cloud(new_imgs, f"DNXL_{row['dnxl_id']}")
                                if uploaded:
                                    final_img_str = (final_img_str + "\n" + uploaded).strip()
                        
                        # Call Service
                        suc, msg = dnxl_service.update_dnxl_progress(
                            row['dnxl_id'],
                            final_details,
                            worker_response,
                            final_img_str
                        )
                        
                        if suc:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

# --- TAB 3: HISTORY (Read Only) ---
with tab3:
    # Logic: Get all where claimed_by = user and status in [cho_duyet, hoan_thanh]
    # Re-fetch mostly correct as 'get_pending_dnxl' filters strictly, but we can reuse 'to_xu_ly'
    # Wait, 'get_pending_dnxl' for 'to_xu_ly' logic: status='moi_tao' OR claimed_by=user
    # So df_all already has them.
    
    hist_stats = ['cho_duyet_ket_qua', 'hoan_thanh']
    df_hist = df_all[df_all['status'].isin(hist_stats)] if not df_all.empty else pd.DataFrame()
    
    if df_hist.empty:
         st.caption("Chưa có lịch sử.")
    else:
        st.dataframe(df_hist[['dnxl_id', 'status', 'deadline', 'created_by', 'worker_response']], hide_index=True)
