import streamlit as st
import time
from utils.ncr_helpers import init_gspread

# ==========================================
# 1. CENTRAL MENU CONFIGURATION
# ==========================================

# Department mapping matching the filenames
DEPARTMENT_PAGES = {
    "fi": "pages/01_fi.py",
    "dv_cuon": "pages/02_dv_cuon.py",
    "dv_npl": "pages/03_dv_npl.py",
    "trang_cat": "pages/04_trang_cat.py",
    "may_i": "pages/05_may_i.py",
    "may_p2": "pages/06_may_p2.py",
    "may_n4": "pages/07_may_n4.py",
    "may_a2": "pages/08_may_a2.py",
    "tp_dau_vao": "pages/09_tp_dau_vao.py",
    "in_d": "pages/10_in_xuong_d.py",
    "cat_ban": "pages/11_cat_ban.py"
}

# Define the menu structure
# roles="all" means everyone.
# departments="all" means everyone.
# If explicit list provided, only those allow-listed (plus admin) can see.
MENU_STRUCTURE = [
    {
        "label": "Tổng quan",
        "icon": "🏠", 
        "expanded": True,
        "items": [
            {
                "label": "Dashboard", 
                "icon": "📊", 
                "path": "Dashboard.py", 
                "roles": ["all"], 
                "departments": ["all"]
            },
            {
                "label": "NCR của tôi", 
                "icon": "🙋", 
                "path": "pages/00_ncr_cua_toi.py", 
                "roles": ["all"], 
                "departments": ["all"],
                "badge_key": "my_ncr"
            }
        ]
    },
    {
        "label": "Nhập liệu (QC Input)",
        "icon": "📝",
        "expanded": False,
        "items": [
             {"label": "Khu vực FI", "path": DEPARTMENT_PAGES["fi"], "departments": ["fi"]},
             {"label": "ĐV Cuộn", "path": DEPARTMENT_PAGES["dv_cuon"], "departments": ["dv_cuon"]},
             {"label": "ĐV NPL", "path": DEPARTMENT_PAGES["dv_npl"], "departments": ["dv_npl"]},
             {"label": "Tráng Cắt", "path": DEPARTMENT_PAGES["trang_cat"], "departments": ["trang_cat"]},
             {"label": "Máy 1", "path": DEPARTMENT_PAGES["may_i"], "departments": ["may_i"]},
             {"label": "Máy P2", "path": DEPARTMENT_PAGES["may_p2"], "departments": ["may_p2"]},
             {"label": "Máy N4", "path": DEPARTMENT_PAGES["may_n4"], "departments": ["may_n4"]},
             {"label": "Máy A2", "path": DEPARTMENT_PAGES["may_a2"], "departments": ["may_a2"]},
             {"label": "TP Đầu Vào", "path": DEPARTMENT_PAGES["tp_dau_vao"], "departments": ["tp_dau_vao"]},
             {"label": "In Xưởng D", "path": DEPARTMENT_PAGES["in_d"], "departments": ["in_d"]},
             {"label": "Cắt Bàn", "path": DEPARTMENT_PAGES["cat_ban"], "departments": ["cat_ban"]},
        ]
    },
    {
        "label": "Phê duyệt",
        "icon": "✅",
        "expanded": True,
        "items": [
            {
                "label": "Phê Duyệt", 
                "icon": "✍️", 
                "path": "pages/50_phe_duyet.py", 
                "roles": ["truong_ca", "truong_bp", "qc_manager", "director", "bgd_tan_phu"],
                "badge_key": "approval"
            },
            {
                "label": "Ban Giám Đốc", 
                "icon": "👑", 
                "path": "pages/99_ban_giam_doc.py", 
                "roles": ["director", "bgd_tan_phu"]
            }
        ]
    },
    {
        "label": "Báo cáo",
        "icon": "📊",
        "expanded": False,
        "items": [
            {
                "label": "Báo Cáo Chung", 
                "icon": "📈", 
                "path": "pages/90_bao_cao.py", 
                "roles": ["qc_manager", "director", "bgd_tan_phu"]
            },
            {
                "label": "QC Giám Sát", 
                "icon": "🔧", 
                "path": "pages/51_qc_giam_sat.py", 
                "roles": ["qc_manager", "director"]
            }
        ]
    },
    {
        "label": "Hệ thống",
        "icon": "⚙️", 
        "expanded": False,
        "items": [
            {
                "label": "Quản lý User", 
                "icon": "👥", 
                "path": "pages/98_quan_ly_user.py", 
                "roles": ["admin"]
            },
            {
                "label": "Kiểm tra hệ thống", 
                "icon": "🩺", 
                "path": "pages/99_kiem_tra_he_thong.py", 
                "roles": ["admin"]
            }
        ]
    }
]

# ==========================================
# 2. CACHED DATA FETCHING
# ==========================================
@st.cache_data(ttl=60)
def fetch_badge_counts(username, role, department):
    """
    Fetch counts for badges. Cached for 60 seconds to reduce DB load.
    Returns: dict {'my_ncr': 0, 'approval': 0}
    """
    counts = {"my_ncr": 0, "approval": 0}
    
    try:
        gc = init_gspread()
        if not gc: return counts
        
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        
        # 1. Count My NCR (Draft/Rejected)
        # Use simple filter if possible, or fetch all and filter df
        # For performance on mobile, we try to be efficient. 
        # Here we mock efficient fetching by loading full data (cached elsewhere usually)
        # In production, we assume `utils.ncr_helpers._get_ncr_data_cached` handles caching.
        from utils.ncr_helpers import _get_ncr_data_cached
        df = _get_ncr_data_cached()
        
        if not df.empty:
            # Normalize
            if 'nguoi_lap_phieu' in df.columns and 'trang_thai' in df.columns:
                df['nguoi_lap_phieu'] = df['nguoi_lap_phieu'].astype(str).str.lower().str.strip()
                df['trang_thai'] = df['trang_thai'].astype(str).str.lower().str.strip()
                
                # My NCR: user is creator AND status in [draft, rejected]
                # Note: 'rejected' might be represented differently, usually status starts with 'draft' or has rejection info?
                # Based on previous context, rejected items revert to 'draft' or specific states?
                # User "My NCR" page usually shows "Cần xử lý".
                my_pending = df[
                    (df['nguoi_lap_phieu'] == username.lower()) & 
                    (df['trang_thai'].isin(['draft', 'tu_choi', 'rejected'])) 
                ]
                counts['my_ncr'] = len(my_pending)
                
        # 2. Count Approvals
        # This is complex as it depends on status mapping.
        # Simplified: Check count of tickets waiting for THIS role.
        # Mapping from role to status
        role_status_map = {
            'truong_ca': 'cho_truong_ca',
            'truong_bp': 'cho_truong_bp',
            'qc_manager': 'cho_qc_manager',
            'director': 'cho_giam_doc',
            'bgd_tan_phu': 'cho_bgd_tan_phu'
        }
        
        if role in role_status_map:
            target_status = role_status_map[role]
            if not df.empty and 'trang_thai' in df.columns:
                 approval_pending = df[df['trang_thai'] == target_status]
                 # Filter by department if needed (e.g. Truong Ca only sees their dept)
                 if role in ['truong_ca', 'truong_bp'] and department:
                     # Assumes mapping to department code exists in data or can be inferred
                     pass # For now, count global queue or refine if needed
                 
                 counts['approval'] = len(approval_pending)

    except Exception as e:
        # Fallback silently or log
        pass
        
    return counts

# ==========================================
# 3. RENDER FUNCTION
# ==========================================
try:
    from streamlit.runtime.scriptrunner import get_script_run_ctx
except ImportError:
    # Fallback for older Streamlit versions (though we expect >= 1.x)
    from streamlit.scriptrunner import get_script_run_ctx

def get_run_id():
    ctx = get_script_run_ctx()
    return ctx.script_run_id if ctx else None

def render_sidebar(user_info):
    """
    Renders the custom mobile-friendly sidebar.
    Must be called at the top of every page.
    Idempotent within a single script run.
    """
    if not user_info:
        return

    # --- IDEMPOTENCY GUARD ---
    # Ensure we only render ONCE per script execution to avoid DuplicateElementId errors
    current_run_id = get_run_id()
    if st.session_state.get("_last_sidebar_run_id") == current_run_id:
        return
    
    # Mark this run as rendered
    st.session_state._last_sidebar_run_id = current_run_id
    
    # --- CSS Styles ---

    # 1. Hide default nav
    # 2. Style buttons for mobile touch
    st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        
        .nav-section-header {
            font-size: 0.85rem;
            font-weight: 600;
            color: #616161;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .stExpander {
            border: none !important;
            box-shadow: none !important;
        }
        
        .stExpander > details > summary {
            padding-left: 0 !important;
            border: none !important;
            color: #424242 !important;
            font-weight: 600 !important;
        }
        
        /* Mobile Touch Targets */
        button[kind="secondaryFormSubmit"] {
            min-height: 48px !important;
        }
        
        /* Active Page Highlight */
        /* Currently difficult to strictly target active st.page_link without JS, 
           but Streamlit adds some native styles. We enhance hover. */
           
    </style>
    """, unsafe_allow_html=True)
    
    if not user_info:
        return

    user_role = user_info.get("role", "staff")
    user_dept = user_info.get("department", "")
    username = user_info.get("username", "")
    
    # --- BADGE DATA ---
    badges = fetch_badge_counts(username, user_role, user_dept)

    with st.sidebar:
        # Header
        st.markdown("### 🧭 NCR Mobile")
        st.caption(f"User: **{user_info.get('name')}** | Role: `{user_role}`")
        st.divider()
        
        # Render Menu
        for group in MENU_STRUCTURE:
            # Check if any item in this group is visible
            visible_items = []
            for item in group["items"]:
                # Role Check
                allowed_roles = item.get("roles", ["all"])
                if "all" not in allowed_roles and user_role not in allowed_roles and user_role != "admin":
                    continue
                
                # Department Check
                allowed_depts = item.get("departments", ["all"])
                if "all" not in allowed_depts and user_dept not in allowed_depts and user_role != "admin":
                    continue
                    
                visible_items.append(item)
            
            if not visible_items:
                continue
                
            # Render Group
            # Use expander for grouping (default expanded or not)
            with st.expander(group["label"], expanded=group.get("expanded", True)):
                for item in visible_items:
                    label = item["label"]
                    
                    # Add Badge if exists
                    badge_key = item.get("badge_key")
                    if badge_key and badges.get(badge_key, 0) > 0:
                        count = badges[badge_key]
                        label = f"{label} ({count})"
                    
                    # Render Link
                    icon = item.get("icon", "📄")
                    st.page_link(item["path"], label=label, icon=icon, use_container_width=True)
        
        # Logout
        st.divider()
        if st.button("🚪 Đăng xuất", use_container_width=True, key="sidebar_logout"):
            st.session_state.user_info = None
            st.rerun()


def hide_default_sidebar_nav():
    """
    Injects CSS to hide the default Streamlit sidebar navigation.
    Used for pages where render_sidebar is not called or as a global fallback.
    """
    st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
    """, unsafe_allow_html=True)
