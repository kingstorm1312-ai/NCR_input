import streamlit as st
import pandas as pd
import gspread
import json
import base64
import time
from datetime import datetime
from utils.ncr_helpers import get_now_vn, init_gspread

# --- CONFIG: DEPARTMENT ROUTING ---
DEPARTMENT_PAGES = {
    "fi": "pages/01_🔍_FI.py",
    "dv_cuon": "pages/02_💿_ĐV_Cuộn.py",
    "dv_npl": "pages/03_📦_ĐV_NPL.py",
    "trang_cat": "pages/04_✂️_Tráng_Cắt.py",
    "may_i": "pages/05_🧵_May_I.py",
    "may_p2": "pages/06_🧵_May_P2.py",
    "may_n4": "pages/07_🧵_May_N4.py",
    "may_a2": "pages/08_🧵_May_A2.py",
    "tp_dau_vao": "pages/09_📦_TP_Đầu_Vào.py",
    "in_d": "pages/10_🖨️_In_Xưởng_D.py",
    "cat_ban": "pages/11_🔪_Cắt_Bàn.py"
}

# --- PAGE SETUP ---
st.set_page_config(page_title="Đại Lục CPC - QC System", page_icon="🏭", layout="centered", initial_sidebar_state="auto")

# --- MOBILE NAVIGATION HELPER ---
st.markdown("""
<style>
    /* Đảm bảo header và nút sidebar rõ ràng trên di động */
    header[data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        z-index: 999999;
    }
</style>
""", unsafe_allow_html=True)

# --- GLOBAL STYLING (CSS) ---
def local_css():
    st.markdown("""
    <style>
        /* Hide Default Streamlit Elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        /* header {visibility: hidden;}  <- Unhide header to show sidebar toggle */
        
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

@st.cache_data(ttl=600)
def get_all_users():
    """Lấy danh sách toàn bộ nhân viên từ sheet USERS"""
    try:
        gc = init_gspread()
        if not gc: return []
        spreadsheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("USERS")
        data = ws.get_all_records()
        return data
    except Exception as e:
        return []

def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def login_user(username, password):
    """Kiểm tra user từ sheet USERS"""
    try:
        gc = init_gspread()
        if not gc: return None
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("USERS")
        users_data = ws.get_all_records()
        
        df_users = pd.DataFrame(users_data)
        
        # Normalize Data
        df_users['username'] = df_users['username'].astype(str).str.strip()
        df_users['password'] = df_users['password'].astype(str).str.strip()
        
        # Case specific normalized column for lookup
        df_users['username_lower'] = df_users['username'].str.lower()
        
        clean_user_lower = str(username).strip().lower()
        clean_pass = str(password).strip()
        
        # Find user (Case Insensitive)
        user = df_users[df_users['username_lower'] == clean_user_lower]
        
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
        # Container simulating a card
        with st.container():
            # Logo Centered (HTML/CSS)
            try:
                img_base64 = get_base64_image("assets/Logo.png")
                st.markdown(
                    f'<div style="text-align: center; margin-bottom: 20px;">'
                    f'<img src="data:image/png;base64,{img_base64}" width="220">'
                    f'</div>',
                    unsafe_allow_html=True
                )
            except:
                 st.markdown("<h2 style='text-align: center;'>ĐẠI LỤC CPC</h2>", unsafe_allow_html=True)
            
            st.markdown("<h3 style='text-align: center; color: #212121;'>HỆ THỐNG QUẢN LÝ CHẤT LƯỢNG (QC)</h3>", unsafe_allow_html=True)
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
            st.image("assets/Logo.png", width=120)
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
        st.caption(f"Hôm nay: {get_now_vn().strftime('%d/%m/%Y')}")

    # Row 1: Metrics (Placeholder)
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Phiếu NCR hôm nay", "0", delta="0")
    with m2:
        st.metric("Hiệu suất", "100%", delta="+0%")
        
    st.divider()

    # Row 2: Quick Actions (Role-Specific Views)
    st.subheader("🚀 Truy cập nhanh")
    
    role = user['role']
    dept_code = user['department']
    has_dept_page = dept_code in DEPARTMENT_PAGES
    
    # --- VIEW 1: DIRECTOR & BGD ---
    if role in ['director', 'bgd_tan_phu']:
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✍️ Phê Duyệt", use_container_width=True, type="primary"):
                st.switch_page("pages/50_✍️_Phê_Duyệt.py")
        with c2:
            if st.button("👑 Ban Giám Đốc", use_container_width=True):
                st.switch_page("pages/99_👑_Ban_Giám_Đốc.py")
        with c3:
            if st.button("📊 Báo Cáo", use_container_width=True):
                st.switch_page("pages/90_📊_Báo_Cáo.py")

    # --- VIEW 2: QC MANAGER & ADMIN ---
    elif role in ['qc_manager', 'admin']:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✍️ Phê Duyệt", use_container_width=True, type="primary"):
                st.switch_page("pages/50_✍️_Phê_Duyệt.py")
        with c2:
            if st.button("🔧 QC Giám Sát", use_container_width=True):
                st.switch_page("pages/51_🔧_QC_Giám_Sát.py")
                
        c3, c4 = st.columns(2)
        with c3:
            if st.button("🙋 NCR Của Tôi", use_container_width=True):
                 st.switch_page("pages/00_🙋_NCR_Của_Tôi.py")
        with c4:
             if has_dept_page:
                 if st.button(f"📥 Nhập Liệu ({dept_code})", use_container_width=True):
                     st.switch_page(DEPARTMENT_PAGES[dept_code])

    # --- VIEW 2: TRƯỞNG CA & TRƯỞNG BP ---
    elif role in ['truong_ca', 'truong_bp']:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✍️ Phê Duyệt", use_container_width=True, type="primary"):
                st.switch_page("pages/50_✍️_Phê_Duyệt.py")
        with c2:
            if st.button("🙋 NCR Của Tôi", use_container_width=True):
                 st.switch_page("pages/00_🙋_NCR_Của_Tôi.py")
        
        # Row 2 for input
        if has_dept_page:
            if st.button(f"📥 Vào trang Nhập Liệu ({dept_code})", use_container_width=True):
                 st.switch_page(DEPARTMENT_PAGES[dept_code])

    # --- VIEW 3: STAFF (DEFAULT) ---
    else:
        c1, c2 = st.columns(2)
        with c1:
            if has_dept_page:
                if st.button(f"📥 Nhập Liệu ({dept_code})", use_container_width=True, type="primary"):
                    st.switch_page(DEPARTMENT_PAGES[dept_code])
            else:
                 st.info("Chưa phân quyền nhập liệu.")
        with c2:
             if st.button("🙋 NCR Của Tôi", use_container_width=True):
                 st.switch_page("pages/00_🙋_NCR_Của_Tôi.py")
    
    # Check Admin Panel visibility
    if role == 'admin':
        st.divider()
        st.info("Admin Control Panel - Danh sách nhân sự")
        
        # Load all users
        all_users = get_all_users()
        if all_users:
            df_all = pd.DataFrame(all_users)
            
            # Group by Department
            if not df_all.empty and 'department' in df_all.columns:
                unique_depts = df_all['department'].unique()
                
                # Display as Expanders
                for dept in unique_depts:
                    dept_users = df_all[df_all['department'] == dept]
                    count = len(dept_users)
                    
                    with st.expander(f"📂 {dept.upper()} ({count} nhân viên)"):
                        # Simple Table
                        display_df = dept_users[['full_name', 'username', 'role']]
                        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Row 3: Visuals (Placeholder)
    st.write("")
    st.subheader("📈 Thống kê sơ bộ")
    
    # Mockup Chart Data
    chart_data = pd.DataFrame({
        "errors": ["Lỗi May", "Lỗi Cắt", "Lỗi In", "Lỗi Vải", "Khác"],
        "count": [12, 8, 5, 3, 2]
    }).set_index("errors")
    
    st.bar_chart(chart_data, color="#C62828")
