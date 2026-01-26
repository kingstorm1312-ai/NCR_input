import pandas as pd
import streamlit as st
from utils.ncr_helpers import (
    get_all_users, 
    update_user_status, 
    update_user_info
)

@st.cache_data(ttl=300)
def load_users():
    """
    Tải danh sách toàn bộ người dùng.
    """
    return get_all_users()

def approve_user(username):
    """
    Phê duyệt tài khoản (status -> active).
    """
    return update_user_status(username, 'active')

def reject_user(username):
    """
    Từ chối hoặc hủy kích hoạt tài khoản (status -> rejected).
    """
    return update_user_status(username, 'rejected')

def update_user_details(username, role, department):
    """
    Cập nhật thông tin phân quyền và bộ phận của người dùng.
    """
    return update_user_info(username, new_role=role, new_dept=department)

def check_admin_access():
    """
    Kiểm tra quyền Admin của user hiện tại.
    """
    if "user_info" not in st.session_state or not st.session_state.user_info:
        return False, "Vui lòng đăng nhập!"
    
    if st.session_state.user_info.get("role") != "admin":
        return False, "Quyền truy cập bị từ chối! Chỉ dành cho Admin."
        
    return True, "Access granted"
