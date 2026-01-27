import os
import glob
import json
import sys

# OLD -> NEW Mapping (Hardcoded for independence from external json issues, or load it)
# Using the map we defined.
OLD_TO_NEW = {
    "pages/01_🔍_FI.py": "pages/01_fi.py",
    "pages/02_💿_ĐV_Cuộn.py": "pages/02_dv_cuon.py",
    "pages/03_📦_ĐV_NPL.py": "pages/03_dv_npl.py",
    "pages/04_✂️_Tráng_Cắt.py": "pages/04_trang_cat.py",
    "pages/05_🧵_May_I.py": "pages/05_may_i.py",
    "pages/06_🧵_May_P2.py": "pages/06_may_p2.py",
    "pages/07_🧵_May_N4.py": "pages/07_may_n4.py",
    "pages/08_🧵_May_A2.py": "pages/08_may_a2.py",
    "pages/09_📦_TP_Đầu_Vào.py": "pages/09_tp_dau_vao.py",
    "pages/10_🖨️_In_Xưởng_D.py": "pages/10_in_xuong_d.py",
    "pages/11_🔪_Cắt_Bàn.py": "pages/11_cat_ban.py",
    "pages/50_✍️_Phê_Duyệt.py": "pages/50_phe_duyet.py",
    "pages/51_🔧_QC_Giám_Sát.py": "pages/51_qc_giam_sat.py",
    "pages/90_📊_Báo_Cáo.py": "pages/90_bao_cao.py",
    "pages/98_⚙️_Quản_Lý_User.py": "pages/98_quan_ly_user.py",
    "pages/99_👑_Ban_Giám_Đốc.py": "pages/99_ban_giam_doc.py",
    "pages/99_🔍_Kiểm_Tra_Hệ_Thống.py": "pages/99_kiem_tra_he_thong.py",
    "pages/00_🙋_NCR_Của_Tôi.py": "pages/00_ncr_cua_toi.py"
}

def verify():
    print("--- STARTING STRICT REFERENCE CHECK ---")
    
    # 1. Check if old files exist
    print("[1] Checking for leftover old files...")
    old_files_exist = False
    for old_path in OLD_TO_NEW.keys():
        if os.path.exists(old_path):
            print(f"❌ FAIL: Old file still exists: {old_path}")
            old_files_exist = True
    if not old_files_exist:
        print("✅ PASS: No old files found.")

    # 2. Check content of all py files for references to old filenames
    print("\n[2] Checking code references...")
    all_py_files = glob.glob("**/*.py", recursive=True)
    refs_found = 0
    
    for fpath in all_py_files:
        if fpath.startswith("tools") or fpath.startswith("venv") or fpath.startswith("tests"):
            continue
            
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            for old_path in OLD_TO_NEW.keys():
                old_name = os.path.basename(old_path) # e.g. "01_🔍_FI.py"
                # Strict check: check for the filename string in content
                if old_name in content:
                    # Ignore rename_map.json references (though we are scanning py files, mapped inside json strings in py?)
                    # If this script is run, it might check itself if not careful, but we skipped tools/
                    print(f"❌ FAIL: Found reference to '{old_name}' in '{fpath}'")
                    refs_found += 1
                    
                # Also check full path if typically used
                # Normalize slashes
                normalized_old_path = old_path.replace("\\", "/")
                if normalized_old_path in content.replace("\\", "/"):
                     print(f"❌ FAIL: Found full path reference to '{normalized_old_path}' in '{fpath}'")
                     refs_found += 1

        except Exception as e:
            print(f"⚠️ Error reading {fpath}: {e}")

    if refs_found == 0:
        print("✅ PASS: 0 confirmed remaining old refs.")
    else:
        print(f"❌ FAIL: Found {refs_found} remaining references.")

if __name__ == "__main__":
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    verify()
