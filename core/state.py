import streamlit as st

def init_session_state(defaults: dict):
    """
    Khởi tạo các key trong st.session_state nếu chưa tồn tại.
    """
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# Cấu hình state mặc định dùng chung cho các trang nhập liệu
DEFAULT_STATE = {
    "buffer_errors": [],
    "header_locked": False,
    "images": [],
    "trace_id": None, # str or None
    "draft": {},
    "last_saved": None # dict or None
}
