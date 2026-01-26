# QC Data Entry App - NCR Input Mobile

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![Status](https://img.shields.io/badge/Status-Active-green.svg)

Ứng dụng Mobile-First giúp nhân viên QC nhập liệu kiểm tra chất lượng sản phẩm từ điện thoại.

## ✨ Tính Năng Chính

### 🎯 Core Features

- **Buffer Logic**: Lưu tạm dữ liệu trước khi save vào Google Sheets
- **Aggregation Logic**: Tự động cộng dồn số lượng lỗi trùng (Error + Location)
- **Flexible Input**: Cho phép nhập lỗi mới không có trong Master Data
- **Smart Severity**: Tự động nhận biết mức độ nghiêm trọng (Critical/Major/Minor)
- **Mobile-First UI**: Giao diện tối ưu cho điện thoại

### 📊 Smart Severity Logic

- **Auto-Lookup**: Tự động lấy severity từ Master Data
- **Severity Badges**: Hiển thị icon trực quan (🔴 Critical, 🟠 Major, 🟡 Minor)
- **Manual Selection**: Chọn severity thủ công cho custom errors
- **Breakdown Metrics**: Phân tích chi tiết theo mức độ

## 🚀 Cách Sử Dụng

### Yêu Cầu Hệ Thống

```bash
Python 3.9+
Streamlit
Pandas
```

### Cài Đặt

```bash
# Clone repository
git clone https://github.com/kingstorm1312-ai/NCR_input.git
cd NCR_input

# Cài đặt dependencies
pip install streamlit pandas

# Cấu hình Secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Sau đó mở .streamlit/secrets.toml và điền thông tin:
# - spreadsheet_id
# - service_account (JSON)
# - cloudinary config

# Chạy app
streamlit run Dashboard.py

# Kiểm tra hệ thống (Smoke Test)
python scripts/smoke_test.py
```

## 📱 Workflow

1. **Điền Header**: Nhập thông tin lô hàng (NCR ID, Sản phẩm, Nhà máy, SL Kiểm)
2. **Lock Header**: Khóa header để focus vào nhập lỗi
3. **Thêm Lỗi**:
   - Chọn lỗi → Severity tự động hiện
   - Hoặc chọn "Lỗi Khác/Mới..." → Nhập tên + chọn severity
4. **Review**: Kiểm tra buffer table và metrics
5. **Save**: Lưu toàn bộ vào Google Sheets

## 🎨 Screenshots

### Detail Entry với Auto Severity

![Detail Section](screenshots/detail_section.png)

### Review Section với Severity Breakdown

![Review Section](screenshots/review_section.png)

## 🔧 Cấu Trúc Dữ Liệu

### Master Data (CONFIG Sheet)

- `NHA_GIA_CONG`: Factory
- `TEN_LOI`: Error Name
- `VI_TRI`: Location
- `MA_VAT_TU`: Product Code
- `MUC_DO`: Severity Level

### Transaction Data (NCR_DATA Sheet)

- `timestamp`, `date`, `week`, `month`
- `user`, `ncr_id`, `contract_id`
- `product_code`, `product_name`, `factory`
- `checked_qty`, `batch_qty`
- `error_name`, `error_location`, `error_severity`, `error_qty`

## 📝 License

MIT License - Free to use and modify

## 👤 Author

**Kingstorm1312-AI**

- GitHub: [@kingstorm1312-ai](https://github.com/kingstorm1312-ai)

## 🙏 Acknowledgments

Built with ❤️ using Streamlit for mobile QC data entry.
