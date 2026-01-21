import streamlit as st

st.set_page_config(page_title="QC Reports", page_icon="📊", layout="wide")

# --- AUTHENTICATION CHECK ---
# Kiểm tra user_info thay vì logged_in để đồng bộ với logic Dashboard
if "user_info" not in st.session_state or not st.session_state.user_info:
    st.warning("⚠️ Vui lòng đăng nhập tại Dashboard trước!")
    st.stop()

# --- RBAC CHECK ---
# Chỉ cho phép Admin hoặc Manager
user_role = st.session_state["user_info"].get("role")

if user_role not in ['admin', 'manager']:
    st.error(f"⛔ Chỉ Admin/Manager mới được xem báo cáo! (Role của bạn: {user_role})")
    st.stop()

# --- REPORT CONTENT ---
st.title("📊 Báo cáo tổng hợp")
st.write(f"Xin chào {st.session_state['user_info']['name']}, đây là trang dành cho quản lý.")

st.info("🚧 Tính năng báo cáo đang được phát triển...")
