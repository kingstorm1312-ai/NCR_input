import streamlit as st

st.set_page_config(
    page_title="QC System Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏭 Hệ thống Quản Lý Chất Lượng (QC System)")
st.divider()

st.markdown("""
### 👋 Chào mừng đến với QC System

Hệ thống hỗ trợ ghi nhận và quản lý dữ liệu CLSP (NCR) tại nhà máy và các đơn vị gia công.

#### 📂 Các chức năng hiện có:
*   👈 **Chọn "Nhập NCR" bên thanh điều hướng** để bắt đầu ghi nhận lỗi.

#### 📈 Thông tin chung
*   **Trạng thái hệ thống**: 🟢 Online
*   **Phiên bản**: 1.0.0
*   **Liên hệ hỗ trợ**: IT Department
""")

st.info("💡 Mẹo: Bạn có thể ẩn/hiện thanh điều hướng bằng cách nhấn vào dấu mũi tên ở góc trên bên trái.")
