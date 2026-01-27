import streamlit as st

def require_login():
    """
    Check if user is logged in. If not, stop execution and warn.
    """
    if "user_info" not in st.session_state or not st.session_state.user_info:
        st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
        st.stop()

def require_dept_access(required_dept):
    """
    Check if user has access to the required department.
    Admin usually has access to everything.
    """
    user_info = st.session_state.user_info
    user_dept = user_info.get("department")
    user_role = user_info.get("role")

    if user_role != 'admin' and user_dept != required_dept:
        st.error(f"⛔ Bạn thuộc bộ phận '{user_dept}', không có quyền truy cập vào '{required_dept}'!")
        if st.button("🔙 Quay lại trang chủ"):
            st.switch_page("Dashboard.py")
        st.stop()
