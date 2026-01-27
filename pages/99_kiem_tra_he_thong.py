"""
Script Kiểm Tra External Dependencies - Google Sheet & Cloudinary
Mục đích: Validate cấu trúc Sheet và kết nối Cloudinary
"""

import streamlit as st
import gspread
import json
import cloudinary
import cloudinary.uploader
from utils.ncr_helpers import COLUMN_MAPPING, init_gspread

st.set_page_config(page_title="🔍 Kiểm Tra Hệ Thống", page_icon="🔍", layout="wide")

st.title("🔍 Kiểm Tra External Dependencies")
st.markdown("Script này kiểm tra Google Sheet structure và Cloudinary config")

# --- AUTHENTICATION CHECK ---
from core.auth import require_admin, get_user_info
require_admin()
user_info = get_user_info()
user_role = user_info.get("role")

# === 1. KIỂM TRA GOOGLE SHEET ===
st.header("📊 1. Kiểm Tra Google Sheet")

try:
    gc = init_gspread()
    if gc:
        sh = gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("NCR_DATA")
        
        # Lấy headers
        headers_raw = ws.row_values(1)
        headers = [str(h).strip().lower() for h in headers_raw]
        
        st.success(f"✅ Kết nối Google Sheet thành công!")
        st.info(f"📋 Sheet có {len(headers)} cột")
        
        # Kiểm tra từng cột cần thiết
        st.subheader("Kiểm tra các cột bắt buộc:")
        
        required_sheet_columns = list(set(COLUMN_MAPPING.values()))
        
        missing_cols = []
        present_cols = []
        
        for col in required_sheet_columns:
            if col.lower() in headers:
                present_cols.append(col)
            else:
                missing_cols.append(col)
        
        # Hiển thị kết quả
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("✅ Cột có sẵn", len(present_cols))
            if present_cols:
                with st.expander("Xem danh sách"):
                    for col in sorted(present_cols):
                        st.text(f"✓ {col}")
        
        with col2:
            st.metric("❌ Cột thiếu", len(missing_cols))
            if missing_cols:
                st.error("⚠️ CẦN BỔ SUNG CÁC CỘT SAU:")
                for col in sorted(missing_cols):
                    st.text(f"✗ {col}")
        
        # Kiểm tra đặc biệt các cột quan trọng
        st.subheader("Kiểm tra cột quan trọng:")
        critical_cols = {
            'don_vi_tinh': 'Đơn vị tính',
            'ly_do_tu_choi': 'Lý do từ chối',
            'hinh_anh': 'Hình ảnh',
            'kp_status': 'Corrective Action Status',
            'kp_assigned_by': 'Người giao CA',
            'kp_assigned_to': 'Người nhận CA',
            'kp_message': 'Thông điệp CA',
            'kp_deadline': 'Deadline CA',
            'kp_response': 'Phản hồi CA'
        }
        
        for col_name, col_desc in critical_cols.items():
            if col_name.lower() in headers:
                st.success(f"✅ {col_desc} ({col_name})")
            else:
                st.error(f"❌ THIẾU: {col_desc} ({col_name})")
        
        # Hiển thị tất cả headers hiện tại
        with st.expander("📋 Xem tất cả headers trên Sheet"):
            st.code("\n".join(headers_raw), language="text")
            
    else:
        st.error("❌ Không thể kết nối Google Sheet")
        
except Exception as e:
    st.error(f"❌ Lỗi khi kiểm tra Google Sheet: {e}")

st.divider()

# === 2. KIỂM TRA CLOUDINARY ===
st.header("☁️ 2. Kiểm Tra Cloudinary Config")

try:
    # Lấy config
    cloud_name = st.secrets.get("cloudinary", {}).get("cloud_name", "")
    api_key = st.secrets.get("cloudinary", {}).get("api_key", "")
    api_secret = st.secrets.get("cloudinary", {}).get("api_secret", "")
    
    if cloud_name and api_key and api_secret:
        st.success("✅ Cloudinary config có sẵn trong secrets")
        
        # Hiển thị thông tin (ẩn secret)
        st.info(f"📦 Cloud Name: `{cloud_name}`")
        st.info(f"🔑 API Key: `{api_key[:4]}...{api_key[-4:]}`")
        st.info(f"🔐 API Secret: `***` (đã ẩn)")
        
        # Khởi tạo Cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
        
        st.success("✅ Cloudinary đã được khởi tạo")
        
        # Test upload (tùy chọn)
        st.subheader("Test Upload (Tùy chọn)")
        st.warning("⚠️ Test upload sẽ tạo file thật trên Cloudinary")
        
        uploaded_file = st.file_uploader("Chọn ảnh để test upload", type=['png', 'jpg', 'jpeg'])
        
        if uploaded_file and st.button("🚀 Test Upload"):
            with st.spinner("Đang upload..."):
                try:
                    # Upload
                    result = cloudinary.uploader.upload(
                        uploaded_file.getvalue(),
                        folder="ncr_test",
                        public_id=f"test_{int(datetime.now().timestamp())}"
                    )
                    
                    st.success("✅ Upload thành công!")
                    st.image(result['secure_url'], caption="Ảnh vừa upload", width=300)
                    st.code(result['secure_url'], language="text")
                    
                except Exception as upload_err:
                    st.error(f"❌ Upload thất bại: {upload_err}")
    else:
        st.error("❌ THIẾU CLOUDINARY CONFIG")
        st.warning("Cần bổ sung vào secrets.toml:")
        st.code("""
[cloudinary]
cloud_name = "your_cloud_name"
api_key = "your_api_key"
api_secret = "your_api_secret"
""", language="toml")
        
except Exception as e:
    st.error(f"❌ Lỗi khi kiểm tra Cloudinary: {e}")

st.divider()

# === 3. TÓM TẮT ===
st.header("📋 Tóm Tắt Kiểm Tra")

st.markdown("""
### ✅ Checklist
- [ ] Google Sheet có đầy đủ cột bắt buộc
- [ ] Cột `don_vi_tinh` tồn tại
- [ ] Các cột Corrective Action (`kp_*`) tồn tại
- [ ] Cloudinary config đầy đủ
- [ ] Test upload Cloudinary thành công

### 🔧 Hướng Dẫn Khắc Phục
**Nếu thiếu cột trên Sheet:**
1. Mở Google Sheet NCR_DATA
2. Thêm các cột thiếu vào header (dòng 1)
3. Refresh trang này để kiểm tra lại

**Nếu thiếu Cloudinary config:**
1. Tạo tài khoản Cloudinary (miễn phí)
2. Lấy cloud_name, api_key, api_secret
3. Thêm vào `.streamlit/secrets.toml` hoặc Streamlit Cloud secrets
""")
