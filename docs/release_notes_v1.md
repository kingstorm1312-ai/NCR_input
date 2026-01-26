# Release Notes - NCR Mobile Project V1.0

Tài liệu này tổng hợp kiến trúc hệ thống, các tính năng an toàn và danh sách các dấu mốc quan trọng (Milestones) trong quá trình phát triển và refactor hệ thống NCR Mobile.

## 🏗️ Tổng quan Kiến trúc (Architecture)

Hệ thống được thiết kế theo hướng module hóa, tách biệt rõ ràng giữa giao diện (UI) và logic xử lý (Service Layer):

### 1. Core Engine & Dept Profiles

- **`core/form_engine.py`**: Engine trung tâm điều phối việc nhập liệu QC. Nó sử dụng cấu hình từ các Profile để thay đổi hành vi (Has AQL, Has Measurements, v.v.) mà không cần sửa code engine.
- **`core/profile.py` & `depts/`**: Định nghĩa cấu trúc `DeptProfile` và đăng ký các bộ phận (FI, May, Tráng Cắt, v.v.).

### 2. Service Layer Modules

Toàn bộ logic nghiệp vụ phức tạp đã được tách khỏi file `.py` của Streamlit pages:

- **`report_service`**: Xử lý tải dữ liệu báo cáo, lọc phiếu hủy và chuẩn bị dữ liệu cho biểu đồ Plotly.
- **`approval_service`**: Quản lý quy trình phê duyệt/từ chối, bao gồm kiểm tra trạng thái (Status Guard).
- **`monitor_service`**: Giám sát các phiếu bị trả về và dữ liệu lịch sử (Legacy).
- **`user_service`**: Quản lý tài khoản người dùng và thắt chặt quyền truy cập Admin.

## 🛡️ Tính năng An toàn (Safety Guards)

### 1. Idempotency & Status Guard

Trong `approval_service`, trước khi thực hiện bất kỳ lệnh `update` nào vào Google Sheets, hệ thống sẽ:

- Đọc trực tiếp trạng thái thực tế từ Sheet.
- Chỉ cho phép cập nhật nếu trạng thái hiện tại khớp với quyền hạn của Role (VD: Trưởng BP chỉ được duyệt phiếu đang ở `cho_truong_bp`).
- Ngăn chặn triệt để lỗi double-click hoặc race condition.

### 2. Dynamic Prefix Mapping

Hệ thống tự động xác định mã tiền tố (Prefix) dựa trên `profile.code` và giá trị phân loại (Khâu):

- VD: Bộ phận `trang_cat` sẽ dùng `X2-TR` cho Tráng và `X2-CA` cho Cắt.
- Logic này được tập trung hóa trong `resolve_prefix` để dễ dàng mở rộng.

## 🚀 Hướng dẫn vận hành (How to run)

### Chạy ứng dụng chính

```bash
streamlit run Dashboard.py
```

### Chạy Smoke Test (Kiểm tra hệ thống)

```bash
python scripts/smoke_test.py
```

## 📍 Danh sách Milestone Commits

Dưới đây là các hash commit đánh dấu việc hoàn thành các giai đoạn quan trọng:

| Giai đoạn | Commit Hash | Mô tả |
| :--- | :--- | :--- |
| **Phase 1** | `90ad857e4e16d4073f15fb56a87e59546096504a` | Đồng bộ hóa UI và Logic cho toàn bộ các bộ phận May & TP. |
| **Phase 2** | `2ee46aeacff4c862a7873936c3afba609e789d6b` | Hoàn thành Migration sang Form Engine & Dynamic Prefix mapping. |
| **Phase 3** | `0e5cd0fc84e253c90d2d1c2afb6c5a6fca1c1976` | Hoàn thành Service Layer Refactor (Report, Approve, Monitor, User). |
| **Phase 4** | `75ea2eaae66480c1fea9d5ecf9f1f5296adbcaf1` | Bổ sung Smoke Test Harness để kiểm tra cấu hình hệ thống. |

---
*Built with Antigravity AI Engine*
