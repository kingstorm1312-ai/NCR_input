import os
import re

# REFACTOR LOGIC
AUTH_IMPORT = """from core.auth import require_login, require_dept_access
from core.master_data import load_config_sheet
from core.gsheets import get_client, smart_append_batch, open_worksheet
"""

AUTH_BLOCK_REGEX = r"""# --- KIỂM TRA ĐĂNG NHẬP ---\s*if "user_info" not in st\.session_state.*?\n    st\.stop\(\)\s*user_info = st\.session_state\.user_info\s*user_dept = user_info\.get\("department"\)\s*user_role = user_info\.get\("role"\)\s*if user_role != 'admin' and user_dept != REQUIRED_DEPT:.*?\n    st\.stop\(\)"""

AUTH_BLOCK_REPLACEMENT = """# --- KIỂM TRA ĐĂNG NHẬP ---
require_login()
require_dept_access(REQUIRED_DEPT)

user_info = st.session_state.user_info
"""

MASTER_DATA_REGEX = r"""# --- TẢI DỮ LIỆU CẤU HÌNH \(MASTER DATA\) ---\s*@st\.cache_data\(ttl=600\)\s*def load_master_data\(\).*?LIST_NOI_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO = load_master_data\(\)"""
MASTER_DATA_REPLACEMENT = """# --- TẢI DỮ LIỆU CẤU HÌNH (MASTER DATA) ---
LIST_NOI_MAY, LIST_LOI, LIST_VI_TRI, DICT_MUC_DO, _ = load_config_sheet()
"""

GSHEETS_INIT_REGEX = r"""gc = init_gspread\(\)"""
GSHEETS_INIT_REPLACEMENT = ""  # Remove it

def refactor_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        
        # 1. ADD AUTHORS IMPORTS
        # Find where to insert usually after internal imports
        # For simplicity, let's insert after "from utils.config ..."
        if "from utils.config import NCR_DEPARTMENT_PREFIXES" in new_content:
             new_content = new_content.replace(
                 "from utils.config import NCR_DEPARTMENT_PREFIXES", 
                 "from utils.config import NCR_DEPARTMENT_PREFIXES\n\n# --- CORE IMPORTS ---\n" + AUTH_IMPORT
             )
        else:
             print(f"⚠️ Could not find injection point in {filepath}")
             
        # 2. REPLACE AUTH BLOCK
        # This regex is tricky, let's look for the start and end patterns if strictly regex fails
        # Or use simple string replacements if the code is identical (which it should be due to copy paste)
        # Let's try simple replacement for the standard block
        
        legacy_auth_start = '# --- KIỂM TRA ĐĂNG NHẬP ---'
        legacy_auth_end = 'st.stop()'
        # Constructing the exact block is hard due to whitespace.
        # Let's try regex with DOTALL
        
        new_content = re.sub(AUTH_BLOCK_REGEX, AUTH_BLOCK_REPLACEMENT, new_content, flags=re.DOTALL)
        
        # 3. REPLACE MASTER DATA BLOCK
        new_content = re.sub(MASTER_DATA_REGEX, MASTER_DATA_REPLACEMENT, new_content, flags=re.DOTALL)
        
        # 4. REMOVE gc = init_gspread()
        new_content = re.sub(GSHEETS_INIT_REGEX, GSHEETS_INIT_REPLACEMENT, new_content)

        # 5. Fix imports if duplicated
        if new_content.count("from core.auth import require_login") > 1:
             # Cleanup specific logic if needed
             pass

        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Refactored: {filepath}")
        else:
            print(f"⏭️ No changes needed or pattern mismatch: {filepath}")

    except Exception as e:
        print(f"❌ Error refactoring {filepath}: {e}")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    targets = [
        "pages/02_dv_cuon.py", "pages/03_dv_npl.py", "pages/04_trang_cat.py", 
        "pages/10_in_xuong_d.py", "pages/11_cat_ban.py", "pages/50_phe_duyet.py",
        "pages/51_qc_giam_sat.py", "pages/90_bao_cao.py", "pages/00_ncr_cua_toi.py"
    ]
    for t in targets:
        refactor_file(t)
