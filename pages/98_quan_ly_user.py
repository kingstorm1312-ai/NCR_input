import streamlit as st
import pandas as pd
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.services.user_service import (
    load_users, 
    approve_user, 
    reject_user, 
    update_user_details
)
from core.auth import require_admin, get_user_info

st.set_page_config(page_title="Quản lý User", page_icon="⚙️", layout="wide")

# --- AUTH CHECK ---
require_admin()
user_info = get_user_info()

# --- CONSTANTS ---
ROLE_OPTIONS = {
    'staff': 'Nhân viên (Staff)',
    'truong_ca': 'Trưởng ca',
    'truong_bp': 'Trưởng bộ phận',
    'qc_manager': 'QC Manager',
    'director': 'Giám đốc',
    'bgd_tan_phu': 'BGĐ Tân Phú',
    'admin': 'Admin (Quản trị)'
}

DEPT_OPTIONS = {
    "fi": "FI",
    "dv_cuon": "ĐV Cuộn",
    "dv_npl": "ĐV NPL",
    "trang_cat": "Tráng Cắt",
    "may_i": "May I",
    "may_p2": "May P2",
    "may_n4": "May N4",
    "may_a2": "May A2",
    "tp_dau_vao": "TP Đầu Vào",
    "in_d": "In Xưởng D",
    "cat_ban": "Cắt Bàn",
    "kho": "Kho",
    "qc": "QC",
    "bao_tri": "Bảo Trì",
    "nhan_su": "Nhân Sự",
    "ke_hoach": "Kế Hoạch",
    "purchase": "Purchase",
    "khac": "Khác"
}

st.title("⚙️ Quản Lý Người Dùng Hệ Thống")
st.markdown(f"Xin chào Admin **{user_info.get('name')}**")

tab1, tab2 = st.tabs(["🆕 Phê Duyệt User (Pending)", "👥 Danh Sách & Phân Quyền"])

# --- TAB 1: APPROVAL ---
with tab1:
    st.subheader("Danh sách tài khoản chờ duyệt")
    
    if st.button("🔄 Refresh List", key="ref_tab1"):
        st.cache_data.clear()
        st.rerun()
        
    all_users = load_users()
    df = pd.DataFrame(all_users)
    
    # Filter pending
    has_pending = False
    if not df.empty:
        # Normalize keys again just in case, though get_all_users does it
        if 'status' in df.columns:
            pending_df = df[df['status'].astype(str).str.lower() == 'pending']
            
            if not pending_df.empty:
                has_pending = True
                st.write(f"Tìm thấy **{len(pending_df)}** yêu cầu mới.")
                
                for idx, row in pending_df.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([2, 2, 1.5])
                        with c1:
                            st.markdown(f"**{row['full_name']}**")
                            st.caption(f"@{row['username']}")
                        with c2:
                            d_name = DEPT_OPTIONS.get(row['department'], row['department'])
                            r_name = ROLE_OPTIONS.get(row['role'], row['role'])
                            st.write(f"🏢 {d_name} | 🔖 {r_name}")
                        with c3:
                            col_b1, col_b2 = st.columns(2)
                            if col_b1.button("✅", key=f"app_{row['username']}", help="Duyệt (Active)"):
                                success, msg = approve_user(row['username'])
                                if success:
                                    st.success(f"Đã duyệt {row['username']}")
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.error(msg)
                                
                            if col_b2.button("❌", key=f"rej_{row['username']}", help="Từ chối (Reject)"):
                                success, msg = reject_user(row['username'])
                                if success:
                                    st.warning(f"Đã từ chối {row['username']}")
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.error(msg)
            else:
                 st.info("✅ Không có yêu cầu nào đang chờ.")
        else:
             st.warning("⚠️ Dữ liệu chưa có cột 'status'.")
    else:
        st.info("Chưa có dữ liệu.")

# --- TAB 2: MANAGEMENT ---
with tab2:
    st.subheader("Danh sách nhân sự đang hoạt động")
    
    col_search, col_dept, col_ref = st.columns([2, 2, 1])
    with col_search:
        search_term = st.text_input("🔍 Tìm kiếm user:", placeholder="Nhập tên hoặc username...")
    with col_dept:
        # Lấy danh sách bộ phận từ DEPT_OPTIONS
        all_depts = list(DEPT_OPTIONS.keys())
        selected_depts = st.multiselect(
            "Lọc theo bộ phận:", 
            options=all_depts,
            format_func=lambda x: DEPT_OPTIONS.get(x, x)
        )
    with col_ref:
        if st.button("🔄 Refresh Data", key="ref_tab2"):
            st.cache_data.clear()
            st.rerun()

    if not df.empty:
        # Filter active
        mask_active = pd.Series([True]*len(df))
        if 'status' in df.columns:
             mask_active = (df['status'].astype(str).str.lower() == 'active') | (df['status'].astype(str).str.strip() == '')
        
        active_users = df[mask_active].copy()
        
        # 1. Dept Filter
        if selected_depts:
            active_users = active_users[active_users['department'].isin(selected_depts)]

        # 2. Search Filter
        if search_term:
            s = search_term.lower()
            active_users = active_users[
                active_users['username'].astype(str).str.lower().str.contains(s) | 
                active_users['full_name'].astype(str).str.lower().str.contains(s)
            ]
        
        st.write(f"Hiển thị **{len(active_users)}** user.")
        
        for idx, row in active_users.iterrows():
            with st.expander(f"🟢 {row['full_name']} ({row['username']}) - {row['department']}", expanded=False):
                with st.form(key=f"edit_{row['username']}"):
                     c1, c2 = st.columns(2)
                     
                     # Dept Select
                     cur_dept = row['department']
                     dept_keys = list(DEPT_OPTIONS.keys())
                     dept_idx = 0
                     if cur_dept in dept_keys:
                         dept_idx = dept_keys.index(cur_dept)
                     else:
                         # Handle unknown dept (add to options temporarily)
                         dept_keys.append(cur_dept)
                         DEPT_OPTIONS[cur_dept] = cur_dept
                         dept_idx = len(dept_keys) - 1
                         
                     new_dept_key = c1.selectbox(
                         "Bộ phận", 
                         dept_keys, 
                         index=dept_idx,
                         format_func=lambda x: DEPT_OPTIONS.get(x, x)
                     )
                     
                     # Role Select
                     cur_role = row['role']
                     role_keys = list(ROLE_OPTIONS.keys())
                     role_idx = 0
                     if cur_role in role_keys:
                         role_idx = role_keys.index(cur_role)
                     
                     new_role_key = c2.selectbox(
                         "Phân quyền (Role)", 
                         role_keys, 
                         index=role_idx,
                         format_func=lambda x: ROLE_OPTIONS.get(x, x)
                     )
                     
                     st.markdown("---")
                     if st.form_submit_button("💾 Cập nhật thông tin"):
                         with st.spinner("Đang lưu..."):
                             success, msg = update_user_details(row['username'], new_role_key, new_dept_key)
                             if success:
                                 st.success(msg)
                                 st.cache_data.clear()
                                 st.rerun()
                             else: st.error(msg)
