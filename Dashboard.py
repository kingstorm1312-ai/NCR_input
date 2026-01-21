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

# --- CONFIG: DEPARTMENT ROUTING ---
DEPARTMENT_PAGES = {
    "fi": "pages/01_🔍_FI.py",
    "dv_cuon": "pages/02_🌀_ĐV_Cuộn.py",
    "dv_npl": "pages/03_📦_ĐV_NPL.py",
    "trang_cat": "pages/04_✂️_Tráng_Cắt.py",
    "may_i": "pages/05_🧵_May_I.py",
    "may_p2": "pages/06_🧵_May_P2.py",
    "may_n4": "pages/07_🧵_May_N4.py",
    "may_a2": "pages/08_🧵_May_A2.py",
    "in_d": "pages/09_🖨️_In_Xưởng_D.py",
    "cat_ban": "pages/10_🔪_Cắt_Bàn.py"
}

def login_user(username, password):
    """Kiểm tra user từ sheet USERS"""
    gc = init_gspread()
    if not gc:
        return None
    
    try:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("USERS")
        users_data = ws.get_all_records()
        
        df_users = pd.DataFrame(users_data)
        
        # --- FIX: Ép kiểu String và xóa khoảng trắng để so sánh chính xác ---
        # Chuyển đổi toàn bộ cột sang string và strip
        df_users['username'] = df_users['username'].astype(str).str.strip()
        df_users['password'] = df_users['password'].astype(str).str.strip()
        
        # Clean input
        clean_user = str(username).strip()
        clean_pass = str(password).strip()
        
        # Tìm user
        user = df_users[df_users['username'] == clean_user]
        
        if not user.empty:
            stored_password = user.iloc[0]['password']
            if clean_pass == stored_password:
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
                        
                        # --- AUTO ROUTING ---
                        # Nếu department có trong map, chuyển trang ngay lập tức
                        user_dept = user['department']
                        if user['role'] != 'admin' and user_dept in DEPARTMENT_PAGES:
                             st.switch_page(DEPARTMENT_PAGES[user_dept])
                        else:
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
