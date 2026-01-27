import streamlit as st
import pandas as pd
import gspread
import json
import base64
import time
from datetime import datetime
from utils.ncr_helpers import get_now_vn, init_gspread, get_all_users, register_user

# --- CONFIG: DEPARTMENT ROUTING ---
# --- CONFIG: DEPARTMENT ROUTING ---
from utils.ui_nav import DEPARTMENT_PAGES, render_sidebar, hide_default_sidebar_nav

# --- PAGE SETUP ---
st.set_page_config(page_title="Đại Lục CPC - QC System", page_icon="🏭", layout="centered", initial_sidebar_state="auto")

# --- HIDE DEFAULT NAV (GLOBAL FIX) ---
hide_default_sidebar_nav()

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



def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def login_user(username, password):
    """Kiểm tra user từ sheet USERS. Trả về (user_info, error_msg)"""
    try:
        gc = init_gspread()
        if not gc: return None, "Không thể kết nối cơ sở dữ liệu."
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
        user_rows = df_users[df_users['username_lower'] == clean_user_lower]
        
        if not user_rows.empty:
            user = user_rows.iloc[0]
            stored_password = user['password']
            
            if clean_pass == stored_password:
                # Check Status if exists
                if 'status' in df_users.columns:
                    status = str(user['status']).strip().lower()
                    if status == 'pending' or status == 'cho_duyet':
                        return None, "⏳ Tài khoản của bạn đang chờ Admin phê duyệt. Vui lòng quay lại sau."
                    if status == 'rejected' or status == 'bi_tu_choi':
                        return None, "❌ Đăng ký của bạn đã bị từ chối. Vui lòng liên hệ bộ phận IT/Admin."
                    if status != 'active' and status != '':
                        return None, f"Tài khoản đang ở trạng thái: {status.upper()}. Vui lòng liên hệ Admin."
                        
                return {
                    "name": user['full_name'],
                    "username": user['username'],
                    "role": user['role'],
                    "department": user['department']
                }, None
            else:
                return None, "❌ Mật khẩu không chính xác. Vui lòng thử lại."
        else:
            return None, "❌ Tên đăng nhập không tồn tại."
            
    except Exception as e:
        return None, f"Lỗi hệ thống: {e}"
    
    return None, "Lỗi không xác định."

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
            
            # --- TOGGLE LOGIN / REGISTER ---
            if "show_register" not in st.session_state:
                st.session_state.show_register = False

            if st.session_state.show_register:
                st.markdown("#### 📝 Đăng ký tài khoản mới")
                with st.form("register_form"):
                    new_user = st.text_input("Tên đăng nhập (Username)*", placeholder="Viết liền, không dấu")
                    new_pass = st.text_input("Mật khẩu*", type="password")
                    confirm_pass = st.text_input("Nhập lại mật khẩu*", type="password")
                    full_name = st.text_input("Tên hiển thị (Họ tên)*", placeholder="Ví dụ: Nguyễn Văn A")
                    
                    # Department Selection
                    dept_keys = ["all"] + list(DEPARTMENT_PAGES.keys())
                    dept_labels = ["VĂN PHÒNG (ALL)"] + [d.upper().replace('_', ' ') for d in DEPARTMENT_PAGES.keys()]
                    sel_dept_idx = st.selectbox("Bộ phận làm việc*", range(len(dept_labels)), format_func=lambda x: dept_labels[x])
                    selected_dept = dept_keys[sel_dept_idx]
                    
                    # Role Selection
                    role_map = {
                        'staff': 'Nhân viên (Staff)',
                        'truong_ca': 'Trưởng ca',
                        'truong_bp': 'Trưởng bộ phận',
                        'qc_manager': 'QC Manager',
                        'director': 'Giám đốc',
                        'bgd_tan_phu': 'BGĐ Tân Phú'
                    }
                    role_keys = list(role_map.keys())
                    sel_role_idx = st.selectbox("Chức vụ*", range(len(role_keys)), format_func=lambda x: role_map[role_keys[x]])
                    selected_role = role_keys[sel_role_idx]
                    
                    st.caption("(*): Thông tin bắt buộc")
                    st.markdown("---")
                    
                    submitted_reg = st.form_submit_button("GỬI ĐĂNG KÝ", type="primary", use_container_width=True)
                    
                    if submitted_reg:
                        if not new_user or not new_pass or not full_name:
                            st.warning("⚠️ Vui lòng điền đầy đủ thông tin (*)")
                        elif new_pass != confirm_pass:
                            st.error("❌ Mật khẩu nhập lại không khớp!")
                        else:
                            with st.spinner("Đang xử lý đăng ký..."):
                                success, msg = register_user(new_user, new_pass, full_name, selected_dept, selected_role)
                                if success:
                                    st.success(msg)
                                    time.sleep(2)
                                    st.session_state.show_register = False
                                    st.rerun()
                                else:
                                    st.error(f"❌ {msg}")
                
                if st.button("⬅️ Quay lại Đăng nhập", use_container_width=True):
                    st.session_state.show_register = False
                    st.rerun()
                    
            else:
                # LOGIN UI
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
                                user, error = login_user(username, password)
                                if user:
                                    st.session_state.user_info = user
                                    st.toast(f"Chào mừng {user['name']}!", icon="👋")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(error)
                
                if st.button("📝 Đăng ký tài khoản mới", use_container_width=True):
                    st.session_state.show_register = True
                    st.rerun()
            
            st.markdown("<div style='text-align: center; color: #9E9E9E; font-size: 12px; margin-top: 20px;'>© 2026 Dai Luc CPC - IT Department</div>", unsafe_allow_html=True)

    with col3:
        pass # Empty right column

# === VIEW 2: DASHBOARD ===
else:
    user = st.session_state.user_info
    
    # --- SIDEBAR ---
    # --- SIDEBAR (Mobile-Friendly) ---
    render_sidebar(user)

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
                st.switch_page("pages/50_phe_duyet.py")
        with c2:
            if st.button("👑 Ban Giám Đốc", use_container_width=True):
                st.switch_page("pages/99_ban_giam_doc.py")
        with c3:
            if st.button("📊 Báo Cáo", use_container_width=True):
                st.switch_page("pages/90_bao_cao.py")

    # --- VIEW 2: QC MANAGER & ADMIN ---
    elif role in ['qc_manager', 'admin']:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✍️ Phê Duyệt", use_container_width=True, type="primary"):
                st.switch_page("pages/50_phe_duyet.py")
        with c2:
            if st.button("🔧 QC Giám Sát", use_container_width=True):
                st.switch_page("pages/51_qc_giam_sat.py")
                
        c3, c4 = st.columns(2)
        with c3:
            if st.button("🙋 NCR Của Tôi", use_container_width=True):
                 st.switch_page("pages/00_ncr_cua_toi.py")
        with c4:
             if has_dept_page:
                 if st.button(f"📥 Nhập Liệu ({dept_code})", use_container_width=True):
                     st.switch_page(DEPARTMENT_PAGES[dept_code])
        
        # Admin Special Button
        if role == 'admin':
            if st.button("⚙️ Quản lý User (Admin)", use_container_width=True):
                st.switch_page("pages/98_quan_ly_user.py")

    # --- VIEW 2: TRƯỞNG CA & TRƯỞNG BP ---
    elif role in ['truong_ca', 'truong_bp']:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✍️ Phê Duyệt", use_container_width=True, type="primary"):
                st.switch_page("pages/50_phe_duyet.py")
        with c2:
            if st.button("🙋 NCR Của Tôi", use_container_width=True):
                 st.switch_page("pages/00_ncr_cua_toi.py")
        
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
                 st.switch_page("pages/00_ncr_cua_toi.py")
    
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


