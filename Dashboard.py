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
from datetime import datetime

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

# --- PAGE SETUP ---
st.set_page_config(page_title="Đại Lục CPC - QC System", page_icon="🏭", layout="wide")

# --- GLOBAL STYLING (CSS) ---
def local_css():
    st.markdown("""
    <style>
        /* Hide Default Streamlit Elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Branding Colors */
        :root {
            --primary-color: #C62828;
            --secondary-color: #212121;
            --bg-color: #FFFFFF;
        }
        
        /* Button Styling */
        .stButton > button {
            background-color: #C62828 !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: bold !important;
            padding: 0.5rem 1rem !important;
        }
        .stButton > button:hover {
            background-color: #B71C1C !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Input Fields styling */
        .stTextInput > div > div > input {
            border: 1px solid #E0E0E0;
            border-radius: 6px;
        }
        
        /* Metric Cards */
        [data-testid="stMetric"] {
            background-color: #F5F5F5;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border: 1px solid #EEEEEE;
        }
        
        /* Custom Card container */
        .css-card {
            background-color: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- AUTHENTICATION LOGIC ---
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
        ws = sh.worksheet("USERS")
        users_data = ws.get_all_records()
        
        df_users = pd.DataFrame(users_data)
        
        # Normalize Data
        df_users['username'] = df_users['username'].astype(str).str.strip()
        df_users['password'] = df_users['password'].astype(str).str.strip()
        
        clean_user = str(username).strip()
        clean_pass = str(password).strip()
        
        # Find user
        user = df_users[df_users['username'] == clean_user]
        
        if not user.empty:
            stored_password = user.iloc[0]['password']
            if clean_pass == stored_password:
                return {
                    "name": user.iloc[0]['full_name'],
                    "username": user.iloc[0]['username'],
                    "role": user.iloc[0]['role'],
                    "department": user.iloc[0]['department']
                }
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {e}")
    
    return None

# --- UI RENDERER ---

if "user_info" not in st.session_state:
    st.session_state.user_info = None

# === VIEW 1: LOGIN SCREEN ===
if st.session_state.user_info is None:
    # Use columns to center the login card
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col1:
        pass # Empty left column
        
    with col2:
        st.write("") # Top spacer
        st.write("") 
        
        # Container simulating a card
        with st.container():
            # Logo
            try:
                st.image("assets/Logo.png", width=200) 
            except:
                st.markdown("## ĐẠI LỤC CPC") # Fallback text
            
            st.markdown("<h3 style='text-align: left; color: #212121;'>HỆ THỐNG QUẢN LÝ CHẤT LƯỢNG (QC)</h3>", unsafe_allow_html=True)
            st.markdown("---")
            
            with st.form("login_form"):
                username = st.text_input("Tên đăng nhập", placeholder="Nhập username...")
                password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu...")
                
                st.write("") # Spacer
                submit = st.form_submit_button("ĐĂNG NHẬP", type="primary", use_container_width=True)
                
                if submit:
                    if not username or not password:
                        st.warning("Vui lòng nhập đầy đủ thông tin.")
                    else:
                        with st.spinner("Đang kiểm tra..."):
                            user = login_user(username, password)
                            if user:
                                st.session_state.user_info = user
                                st.toast(f"Chào mừng {user['name']}!", icon="👋")
                                time.sleep(0.5)
                                
                                # Auto Routing
                                user_dept = user['department']
                                if user['role'] != 'admin' and user_dept in DEPARTMENT_PAGES:
                                     st.switch_page(DEPARTMENT_PAGES[user_dept])
                                else:
                                     st.rerun()
                            else:
                                st.error("Sai tên đăng nhập hoặc mật khẩu!")
            
            st.markdown("<div style='text-align: center; color: #9E9E9E; font-size: 12px; margin-top: 20px;'>© 2026 Dai Luc CPC - IT Department</div>", unsafe_allow_html=True)

    with col3:
        pass # Empty right column

# === VIEW 2: DASHBOARD ===
else:
    user = st.session_state.user_info
    
    # --- SIDEBAR ---
    with st.sidebar:
        try:
            st.image("assets/Logo.png", width=150)
        except:
            st.title("ĐẠI LỤC CPC")
            
        st.divider()
        st.markdown(f"**Xin chào, {user['name']}**")
        st.caption(f"Bộ phận: *{user['department']}*")
        
        # Badge style role
        role_color = "red" if user['role'] == 'admin' else "blue"
        st.markdown(f":{role_color}[Vai trò: {user['role'].upper()}]")
        
        st.write("")
        st.write("")
        if st.button("Đăng xuất", use_container_width=True):
            st.session_state.user_info = None
            st.rerun()

    # --- MAIN CONTENT ---
    # Header
    c_header, c_date = st.columns([3, 1])
    with c_header:
        st.title("📊 Dashboard Tổng Quan")
    with c_date:
        st.caption(f"Hôm nay: {datetime.now().strftime('%d/%m/%Y')}")

    # Row 1: Metrics (Placeholder)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Phiếu NCR hôm nay", "0", delta="0")
    with m2:
        st.metric("Lỗi nghiêm trọng", "0", delta_color="inverse")
    with m3:
        st.metric("Hiệu suất", "100%", delta="+0%")
        
    st.divider()
    
    # Row 2: Quick Actions
    st.subheader("🚀 Truy cập nhanh")
    
    if user['role'] == 'admin':
        st.info("Admin Control Panel")
        row_a1 = st.columns(4)
        buttons = list(DEPARTMENT_PAGES.items())
        
        # Simple grid for admin
        for i, (dept_code, page_path) in enumerate(buttons):
            col = row_a1[i % 4]
            with col:
                if st.button(f"Go to {dept_code.upper()}", key=f"btn_{dept_code}", use_container_width=True):
                    st.switch_page(page_path)
    else:
        # Staff View
        dept_code = user['department']
        if dept_code in DEPARTMENT_PAGES:
            st.success(f"Bạn đang làm việc tại: {dept_code.upper()}")
            if st.button("👉 BẮT ĐẦU NHẬP LIỆU NGAY", type="primary", use_container_width=True):
                st.switch_page(DEPARTMENT_PAGES[dept_code])
        else:
            st.warning("Tài khoản chưa được phân quyền vào trang nhập liệu.")

    # Row 3: Visuals (Placeholder)
    st.write("")
    st.subheader("📈 Thống kê sơ bộ")
    
    # Mockup Chart Data
    chart_data = pd.DataFrame({
        "errors": ["Lỗi May", "Lỗi Cắt", "Lỗi In", "Lỗi Vải", "Khác"],
        "count": [12, 8, 5, 3, 2]
    }).set_index("errors")
    
    st.bar_chart(chart_data, color="#C62828")
