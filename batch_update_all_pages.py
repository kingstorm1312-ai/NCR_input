"""
Batch update all 11 NCR department pages:
1. Add import upload_images_to_drive
2. Change nguon_goc from selectbox to text_input
3. Add mo_ta_loi text_area  
4. Add image upload
5. Fix save logic with 26-column order
"""
import re
import os

# 26-column template (positions after adding mo_ta_loi at 13, duyet_bgd_tan_phu at 24, hinh_anh at 26)
COLUMN_TEMPLATE = """                    rows.append([
                        now.strftime("%Y-%m-%d %H:%M:%S"),  # 1. ngay_lap
                        so_phieu,                           # 2. so_phieu_ncr
                        hop_dong,                           # 3. hop_dong
                        ma_vt,                              # 4. ma_vat_tu
                        ten_sp,                             # 5. ten_sp
                        {phan_loai},                        # 6. phan_loai
                        nguon_goc,                          # 7. nguon_goc
                        err['ten_loi'],                     # 8. ten_loi
                        err['vi_tri'],                      # 9. vi_tri_loi
                        err['sl_loi'],                      # 10. so_luong_loi
                        sl_kiem,                            # 11. so_luong_kiem
                        err['muc_do'],                      # 12. muc_do
                        mo_ta_loi,                          # 13. mo_ta_loi (NEW)
                        sl_lo,                              # 14. so_luong_lo_hang
                        nguoi_lap,                          # 15. nguoi_lap_phieu
                        nguon_goc,                          # 16. noi_gay_loi
                        'cho_truong_ca',                    # 17. trang_thai
                        now.strftime("%Y-%m-%d %H:%M:%S"),  # 18. thoi_gian_cap_nhat
                        '',                                 # 19. duyet_truong_ca
                        '',                                 # 20. duyet_truong_bp
                        '',                                 # 21. y_kien_qc
                        '',                                 # 22. duyet_qc_manager
                        '',                                 # 23. duyet_giam_doc
                        '',                                 # 24. duyet_bgd_tan_phu (NEW)
                        '',                                 # 25. ly_do_tu_choi
                        hinh_anh_links                      # 26. hinh_anh (NEW - LAST)
                    ])"""

PAGES = [
    ('01_🔍_FI.py', "''"),  # phan_loai empty for FI
    ('02_🌀_ĐV_Cuộn.py', "''"),
    ('03_📦_ĐV_NPL.py', "''"),
    ('04_✂️_Tráng_Cắt.py', 'phan_loai'),  # dynamic for Trang Cat
    ('05_🧵_May_I.py', "''"),
    ('06_🧵_May_P2.py', "''"),
    ('07_🧵_May_N4.py', "''"),
    ('08_🧵_May_A2.py', "''"),
    ('09_📦_TP_Đầu_Vào.py', "''"),
    ('10_🖨️_In_Xưởng_D.py', "''"),
    ('11_🔪_Cắt_Bàn.py', "''"),
]

pages_dir = 'pages'
count = 0

for page_name, phan_loai_value in PAGES:
    filepath = os.path.join(pages_dir, page_name)
    
    if not os.path.exists(filepath):
        print(f"⏭️  Skipped {page_name} (not found)")
        continue
    
    print(f"Processing {page_name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes = []
    
    # 1. Add import if not exists
    if 'upload_images_to_drive' not in content:
        content = content.replace(
            'from utils.ncr_helpers import format_contract_code, render_input_buffer_mobile',
            'from utils.ncr_helpers import format_contract_code, render_input_buffer_mobile, upload_images_to_drive'
        )
        changes.append("import")
    
    # 2. Change nha_may/nha_cung_cap selectbox to nguon_goc text_input
    # Pattern: find selectbox for supplier/factory and replace with text_input
    content = re.sub(
        r'nha_may = st\.selectbox\("Nơi may / Nhà GC", \[""\] \+ LIST_NHA_MAY, disabled=disable_hd\)',
        'nguon_goc = st.text_input("Nguồn gốc", placeholder="VD: Nhà máy A", disabled=disable_hd)',
        content
    )
    content = re.sub(
        r'nha_cung_cap = st\.selectbox\("Nhà CC", \[""\] \+ LIST_NHA_CUNG_CAP, disabled=disable_hd\)',
        'nguon_goc = st.text_input("Nguồn gốc", placeholder="VD: NCC A", disabled=disable_hd)',
        content
    )
    if 'nguon_goc' in content:
        changes.append("nguon_goc")
    
    # 3. Add mo_ta_loi text_area (after sl_lo row)
    # Find pattern after sl_lo and before image or lock section
    if 'mo_ta_loi' not in content:
        # Insert mo_ta_loi after the c3/c4 columns block (after sl_lo)
        pattern = r'(sl_lo = st\.number_input\("SL Lô", min_value=0, value=0, disabled=disable_hd\)\s*)\n(\s*)\n(\s*# Lock Logic|# ROW)'
        replacement = r'\1\n\2\n\2# NEW: Mô tả lỗi (chi tiết)\n\2mo_ta_loi = st.text_area("Mô tả lỗi (chi tiết)", placeholder="Nhập mô tả chi tiết về lỗi...", disabled=disable_hd, height=100)\n\2\n\3'
        content = re.sub(pattern, replacement, content)
        changes.append("mo_ta_loi")
    
    # 4. Add image upload if not exists
    if 'uploaded_images = st.file_uploader' not in content:
        # Insert before lock logic
        lock_pattern = r'(\s+)(# Lock Logic\s*\n\s*st\.write\(""\))'
        img_code = r'\1# Image Upload\n\1st.markdown("**📷 Hình ảnh:**")\n\1uploaded_images = st.file_uploader(\n\1    "Chọn ảnh minh họa",\n\1    type=[\'png\', \'jpg\', \'jpeg\'],\n\1    accept_multiple_files=True,\n\1    disabled=disable_hd,\n\1    key="img_{0}"\n\1)\n\1\n\1\2'
        img_key = page_name.split('_')[0]  # Use page number as unique key
        content = re.sub(lock_pattern, img_code.format(img_key), content)
        changes.append("image_upload")
    
    # 5. Add upload images call in save logic
    if 'hinh_anh_links = ""' not in content:
        save_pattern = r'(with st\.spinner\("Đang lưu\.\.\."\):\s*)\n(\s*)sh = gc'
        upload_code = r'\1\n\2hinh_anh_links = ""\n\2if uploaded_images:\n\2    hinh_anh_links = upload_images_to_drive(uploaded_images, so_phieu)\n\2\n\2sh = gc'
        content = re.sub(save_pattern, upload_code, content)
        changes.append("upload_call")
    
    # 6. Fix column order (26 columns)
    # Replace entire rows.append block
    column_code = COLUMN_TEMPLATE.format(phan_loai=phan_loai_value)
    pattern = r'rows\.append\(\[\s*now\.strftime.*?\]\)'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, column_code.strip(), content, flags=re.DOTALL)
        changes.append("column_order")
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✓ Updated: {', '.join(changes)}")
    count += 1

print(f"\n✅ Successfully updated {count} pages!")
