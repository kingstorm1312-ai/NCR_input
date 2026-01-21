import streamlit as st
import gspread
import pandas as pd
import json
import time

st.set_page_config(
    page_title="QC System Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- UTILS: CONNECT TO GOOGLE SHEETS ---
@st.cache_resource
def init_gspread():
    """Khởi tạo gspread client từ secrets"""
    try:
        creds_str = st.secrets["connections"]["gsheets"]["service_account"]
        
        if isinstance(creds_str, str):
            credentials_dict = json.loads(creds_str, strict=False)
        else:
            credentials_dict = creds_str
            
        gc = gspread.service_account_from_dict(credentials_dict)
        return gc
    except Exception as e:
        st.error(f"Lỗi kết nối System: {e}")
        return None

def login_user(username, password):
    """Kiểm tra user từ sheet USERS"""
    gc = init_gspread()
    if not gc:
        return None
    
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        # Giả định sheet USERS có các cột: username, password, name, role, department
        ws = sh.worksheet("USERS")
        users_data = ws.get_all_records()
        
        df_users = pd.DataFrame(users_data)
        
        # Tìm user
        user = df_users[df_users['username'] == username]
        
        if not user.empty:
            # Check password (ở production nên dùng hash, demo dùng plain text)
            stored_password = str(user.iloc[0]['password'])
            if str(password) == stored_password:
                return {
                    "name": user.iloc[0]['name'],
                    "username": user.iloc[0]['username'],
                    "role": user.iloc[0]['role'],
                    "department": user.iloc[0]['department']
                }
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {e}")
    
    return None

# --- MAIN DASHBOARD LOGIC ---

if "user_info" not in st.session_state:
    st.session_state.user_info = None

if st.session_state.user_info is None:
    # === GIAO DIỆN ĐĂNG NHẬP ===
    st.title("🔐 Đăng Nhập Hệ Thống")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            submit = st.form_submit_button("Đăng nhập", type="primary", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.warning("Vui lòng nhập đầy đủ thông tin.")
                else:
                    user = login_user(username, password)
                    if user:
                        st.session_state.user_info = user
                        st.success(f"Xin chào {user['name']}!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Sai tên đăng nhập hoặc mật khẩu!")
else:
    # === GIAO DIỆN SAU KHI LOGIN ===
    user = st.session_state.user_info
    
    st.title(f"👋 Xin chào, {user['name']}")
    st.caption(f"Role: {user['role']} | Dept: {user['department']}")
    st.divider()

    st.markdown("""
    ### 🏭 Hệ thống Quản Lý Chất Lượng (QC System)
    Chọn chức năng bên thanh điều hướng để bắt đầu.
    """)
    
    # Hiển thị thông báo quyền truy cập
    if user['role'] == 'admin':
        st.success("🛡️ Bạn có quyền Admin: Truy cập toàn bộ hệ thống.")
    else:
        st.info(f"👤 Bạn có quyền Staff: Truy cập chức năng của bộ phận **{user['department']}**.")

    st.divider()
    
    if st.button("Đăng xuất", type="secondary"):
        st.session_state.user_info = None
        st.rerun()
