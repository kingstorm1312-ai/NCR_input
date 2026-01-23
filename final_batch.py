"""Final batch: Update 5 remaining pages with correct phan_loai options"""
import re

# Page configs with phan_loai lists
CONFIGS = {
    '09_📦_TP_Đầu_Vào.py': {
        'phan_loai_options': '["", "Túi TP", "NPL"]',
        'img_key': 'img_tp',
        'nha_may_label': 'Nơi may / NCC'
    },
    '02_🌀_ĐV_Cuộn.py': {
        'phan_loai_options': '["", "Cuộn màng", "Cuộn PP", "Cuộn VKD", "Cuộn RPET", "Cuộn giấy", "Cuộn in", "Cuộn HDPE"]',
        'img_key': 'img_cuon',
        'nha_may_label': 'Nơi may / NCC'
    },
    '03_📦_ĐV_NPL.py': {
        'phan_loai_options': '["", "BXD", "Chỉ", "Cuộn foam", "Cuộn lưới", "Cuộn VKD", "Dây đai", "Dây dù", "Dây kéo, đầu kéo", "Dây viền", "Dây rút", "Dây nẹp", "Đế nhựa", "Giấy carton", "Túi giấy", "Giấy tấm pallet", "Dây thun", "Dây Thừng", "Cuộn in", "Khay", "Hộp", "Manh", "Nắp", "Nẹp", "Nhựa", "Nút", "Ống nhựa", "Tấm lót", "Tấm nhựa", "Tem", "Thùng", "Túi poly", "Túi pp"]',
        'img_key': 'img_npl',
        'nha_may_label': 'Nhà cung cấp'
    },
    '10_🖨️_In_Xưởng_D.py': {
        'phan_loai_options': '["", "In", "Siêu Âm"]',
        'img_key': 'img_in',
        'nha_may_label': 'Nhà cung cấp'
    },
}

# 26-column template
SAVE_TEMPLATE = """                hinh_anh_links = ""
                if uploaded_images:
                    hinh_anh_links = upload_images_to_drive(uploaded_images, so_phieu)
                
                sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
                ws = sh.worksheet("NCR_DATA")
                
                now = datetime.now()
                rows = []
                for err in st.session_state.buffer_errors:
                    rows.append([
                        now.strftime("%Y-%m-%d %H:%M:%S"),  # 1. ngay_lap
                        so_phieu,                           # 2. so_phieu_ncr
                        hop_dong,                           # 3. hop_dong
                        ma_vt,                              # 4. ma_vat_tu
                        ten_sp,                             # 5. ten_sp
                        phan_loai,                          # 6. phan_loai
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
                        hinh_anh_links                      # 26. hinh_anh (NEW)
                    ])"""

for page_name, config in CONFIGS.items():
    filepath = f'pages/{page_name}'
    print(f'Processing {page_name}...')
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace nha_may with nguon_goc
    content = re.sub(
        r'nha_may = st\.selectbox\(".*?", \[""\] \+ LIST_NHA_MAY, disabled=disable_hd\)',
        f'nguon_goc = st.text_input("Nguồn gốc", placeholder="VD: NCC A", disabled=disable_hd)',
        content
    )
    
    # Add phan_loai, mo_ta_loi, image BEFORE "# Lock Logic"
    ui_addition = f'''
    # Phân loại
    phan_loai = st.selectbox("Phân loại", {config['phan_loai_options']}, disabled=disable_hd)
    
    # Mô tả lỗi
    mo_ta_loi = st.text_area("Mô tả lỗi (chi tiết)", placeholder="Nhập mô tả chi tiết về lỗi...", disabled=disable_hd, height=100)
    
    # Image Upload
    st.markdown("**📷 Hình ảnh:**")
    uploaded_images = st.file_uploader(
        "Chọn ảnh minh họa",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        disabled=disable_hd,
        key="{config['img_key']}"
    )

    # Lock Logic'''
    
    content = re.sub(
        r'(\s+sl_lo = st\.number_input.*)\r?\n\s*\r?\n\s*# Lock Logic',
        r'\1\n' + ui_addition,
        content
    )
    
    # Fix save logic - find and replace entire save block
    content = re.sub(
        r'(with st\.spinner\("Đang lưu\.\.\."\):\s*\r?\n)\s*sh = gc',
        r'\1' + SAVE_TEMPLATE.replace('phan_loai', 'phan_loai') + '\n                sh = gc',
        content
    )
    
    # Replace old column references
    content = re.sub(r"nha_may,\s+# 7\. nguon_goc", "nguon_goc,                          # 7. nguon_goc", content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'  ✓ Updated {page_name}')

print('\n✅ Done! 4 pages updated (TP, Cuộn, NPL, In)')
