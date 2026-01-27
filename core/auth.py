import streamlit as st

def require_login():
    """
    Check if user is logged in. If not, stop execution and warn.
    Also handles centralized sidebar injection.
    """
    if "user_info" not in st.session_state or not st.session_state.user_info:
        st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
        if st.button("🏠 Quay về trang Đăng nhập"):
            st.switch_page("Dashboard.py")
        st.stop()
        
    # Inject Mobile Sidebar (Centralized)
    # utils.ui_nav.render_sidebar is idempotent per script run (via get_script_run_ctx)
    from utils.ui_nav import render_sidebar
    render_sidebar(st.session_state.user_info)
    
    return st.session_state.user_info

def get_user_info():
    """
    Ensures user is logged in and returns user_info.
    Pattern: user_info = get_user_info()
    """
    require_login()
    return st.session_state.user_info

def require_dept_access(required_dept):
    """
    Check if user has access to the required department.
    Admin usually has access to everything.
    """
    user_info = require_login()
    user_dept = user_info.get("department")
    user_role = user_info.get("role")

    if user_role != 'admin' and user_dept != required_dept and user_dept != 'all':
        st.error(f"⛔ Bạn thuộc bộ phận '{user_dept}', không có quyền truy cập vào '{required_dept}'!")
        if st.button("🔙 Quay lại trang chủ"):
            st.switch_page("Dashboard.py")
        st.stop()
    return user_info

def require_admin():
    """
    Strict guard for Admin role.
    """
    user_info = require_login()
    if user_info.get("role") != "admin":
        st.error("⛔ Quyền truy cập bị từ chối! Trang này chỉ dành cho Admin.")
        if st.button("🔙 Quay lại trang chủ"):
            st.switch_page("Dashboard.py")
        st.stop()
    return user_info

def require_roles(allowed_roles):
    """
    Strict guard for specified roles.
    """
    user_info = require_login()
    if user_info.get("role") not in allowed_roles and user_info.get("role") != "admin":
        st.error(f"⛔ Bạn không có quyền truy cập trang này! (Quyền yêu cầu: {', '.join(allowed_roles)})")
        if st.button("🔙 Quay lại trang chủ"):
            st.switch_page("Dashboard.py")
        st.stop()
    return user_info
