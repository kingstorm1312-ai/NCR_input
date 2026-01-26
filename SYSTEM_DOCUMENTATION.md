# SYSTEM DOCUMENTATION & DATA FLOW

## 1. Overview

Hệ thống **NCR Mobile** quản lý quy trình tạo, phê duyệt và xử lý các phiếu NCR (Non-Conformance Report) trong nhà máy. Hệ thống sử dụng **Streamlit** (Frontend) và **Google Sheets** (Backend/Database).

### Kiến trúc Hệ thống (System Architecture)

Hệ thống được thiết kế theo mô hình **Service-Oriented Architecture** với các thành phần chính:

#### Core Layer

- **`core/form_engine.py`**: Engine trung tâm xử lý logic nhập liệu QC, được điều khiển bởi Department Profiles
- **`core/profile.py`**: Định nghĩa cấu trúc `DeptProfile` dataclass
- **`depts/`**: Các module profile cho từng bộ phận (FI, May, Tráng-Cắt, Xưởng In, v.v.)

#### Service Layer

Tách biệt hoàn toàn Business Logic khỏi UI:

- **`core/services/report_service.py`**: Xử lý báo cáo và biểu đồ thống kê
- **`core/services/approval_service.py`**: Quản lý quy trình phê duyệt/từ chối với Status Guard
- **`core/services/monitor_service.py`**: Giám sát phiếu bị trả về và dữ liệu legacy
- **`core/services/user_service.py`**: Quản lý tài khoản và phân quyền

#### UI Layer

- **`Dashboard.py`**: Trang chủ, đăng nhập, đăng ký
- **`pages/01-11_*.py`**: Các trang nhập liệu theo bộ phận (sử dụng form_engine)
- **`pages/50_phe_duyet.py`**: Trang phê duyệt NCR
- **`pages/51_qc_giam_sat.py`**: Trang giám sát QC
- **`pages/90_bao_cao.py`**: Báo cáo tổng hợp
- **`pages/98_quan_ly_user.py`**: Quản lý người dùng (Admin only)

## 2. Data Schema (Google Sheets)

Dữ liệu chính nằm trong sheet `NCR_DATA`.
Mỗi dòng đại diện cho một **Lỗi** (Error Row). Một phiếu NCR (`so_phieu_ncr`) có thể bao gồm nhiều dòng lỗi.

### Key Columns

- `so_phieu_ncr`: Mã định danh phiếu (Primary Key cho nhóm lỗi). Format: `[PREFIX]-[YYMMDD]-[SEQ]`
- `trang_thai`: Trạng thái hiện tại của phiếu
- `bo_phan`: Bộ phận chủ quản (được extract từ prefix trong `so_phieu_ncr`)
- `kp_status`, `kp_assigned_to`: Theo dõi hành động khắc phục (Corrective Action)
- `duyet_truong_ca`, `duyet_truong_bp`, `duyet_qc_manager`, `duyet_giam_doc`, `duyet_bgd_tan_phu`: Lưu thông tin người duyệt tại từng cấp

### Dynamic Prefix Mapping

Hệ thống sử dụng **Dynamic Prefix** để phân biệt khâu/chuyền trong cùng một bộ phận:

| Bộ phận | Profile Code | Prefix ví dụ | Quy tắc |
|---------|-------------|--------------|---------|
| Tráng-Cắt | `trang_cat` | `X2-TR`, `X2-CA` | Dựa vào khâu (Tráng/Cắt) |
| Xưởng In | `in_d` | `XG-IN`, `XG-SA` | Dựa vào khâu (In/Sao) |
| FI/May/TP | Static | `FI`, `MAY-I`, `TP-DV` | Prefix cố định |

Logic mapping được centralize trong `core/form_engine.py` → `resolve_prefix()`

## 3. Workflow & Status Lifecycle

### A. Quy trình Phê duyệt Chuẩn (Happy Path)

1. **Draft (`draft`)**: Nhân viên tạo phiếu (hoặc bị trả về)
2. **Chờ Trưởng Ca (`cho_truong_ca`)**: Trưởng ca duyệt sơ bộ
3. **Chờ Trưởng BP (`cho_truong_bp`)**: Trưởng bộ phận duyệt
4. **Chờ QC Manager (`cho_qc_manager`)**: QC Manager đánh giá, phân loại lỗi
5. **Chờ Giám Đốc (`cho_giam_doc`)**: Giám đốc phê duyệt phương án xử lý
6. **Chờ BGĐ Tân Phú (`cho_bgd_tan_phu`)**: (Tùy chọn) Cấp cao nhất duyệt
7. **Hoàn thành (`hoan_thanh`)**: Quy trình kết thúc

### B. Quy trình Từ Chối (Rejection)

Nếu bất kỳ cấp nào từ chối, phiếu sẽ quay về trạng thái **`draft`** để người tạo chỉnh sửa và gửi lại.

**Safety Mechanism - Idempotency Guard:**

- Trước khi approve/reject, hệ thống đọc trực tiếp trạng thái từ Sheet
- Chỉ cho phép cập nhật nếu `trang_thai` hiện tại khớp với quyền hạn của Role
- Ngăn chặn double-click và race condition

### C. Quy trình Hủy Phiếu (Cancellation)

- **Trạng thái:** `da_huy`
- **Trigger:** Nhân viên bấm "Hủy phiếu" khi phiếu đang ở trạng thái `draft`
- **Logic:**
  - Dữ liệu **KHÔNG** bị xóa khỏi Sheet
  - Cột `trang_thai` được cập nhật thành `da_huy`
  - **Critical Rule:** Các phiếu `da_huy` phải bị **LOẠI BỎ HOÀN TOÀN** khỏi các báo cáo thống kê, biểu đồ và KPI

### D. Logic Skip Level (Rút gọn quy trình)

Một số bộ phận thiếu nhân sự (Trưởng BP) sẽ áp dụng quy trình rút gọn:

- **Từ Trưởng Ca (`cho_truong_ca`)** -> Nhảy thẳng lên **QC Manager (`cho_qc_manager`)**
- **Danh sách áp dụng:** `FI`, `ĐV Cuộn`, `ĐV NPL`, `TP Đầu Vào`, và các xưởng `May` (I, P2, N4, A2)
- **Cấu hình:** Được định nghĩa trong `utils/ncr_helpers.py` biến `DEPARTMENTS_SKIP_BP`

## 4. Sub-Process: Corrective Action (Hành động khắc phục)

QC Manager hoặc Director có thể giao task khắc phục cho bộ phận khác:

- Trạng thái phiếu chuyển sang: `khac_phuc_[ROLE_NGUOI_NHAN]`
- Phiếu tạm thời rời khỏi luồng phê duyệt chính
- Sau khi khắc phục xong -> Được xác nhận -> Quay lại luồng phê duyệt

## 5. Reporting Rules (Dành cho AI Agents)

Khi thực hiện query hoặc tạo báo cáo từ `NCR_DATA`:

1. **Luôn filter loại bỏ `da_huy`**:

   ```python
   df = df[df['trang_thai'] != 'da_huy']
   ```

2. **Đếm số lượng phiếu:** Phải group by `so_phieu_ncr` trước khi đếm (vì 1 phiếu có nhiều dòng)

3. **Hierarchy:** `bo_phan` (Bộ phận chính) -> Prefix mã phiếu (Khâu/Chuyền chi tiết)

4. **Service Layer Usage:**
   - Sử dụng `report_service.get_report_data()` thay vì load trực tiếp từ Sheet
   - Các hàm prepare sẽ tự động xử lý filtering và aggregation đúng cách

## 6. User Management System

### A. Đăng ký & Tài khoản

- **Status (Trạng thái):**
  - `active`: Tài khoản đã được duyệt, có thể đăng nhập và sử dụng hệ thống
  - `pending`: Tài khoản mới đăng ký, đang chờ Admin phê duyệt (Không thể đăng nhập)
  - `rejected`: Tài khoản bị từ chối hoặc bị khóa
  
- **Quy trình:**
  1. Người dùng điền form "Đăng ký" trên Dashboard
  2. Hệ thống tạo dòng mới trong sheet `USERS` với `status='pending'`
  3. Admin truy cập trang Quản lý User để duyệt (`active`) hoặc từ chối (`rejected`)

### B. Admin Dashboard (`pages/98_quan_ly_user.py`)

- **Quyền hạn:** Chỉ có tài khoản với `role='admin'` mới truy cập được trang này (hardened via `user_service.check_admin_access()`)
- **Chức năng chính:**
  - **Tab 1 - Phê Duyệt:** Hiển thị danh sách user `pending`. Admin có thể duyệt hoặc từ chối
  - **Tab 2 - Danh Sách:** Hiển thị toàn bộ user `active`. Hỗ trợ tìm kiếm và chỉnh sửa `role` (Chức vụ), `department` (Bộ phận)

## 7. Testing & Quality Assurance

### Smoke Test Harness

Chạy smoke test để kiểm tra cấu hình hệ thống:

```bash
python scripts/smoke_test.py
```

Test cases:

- Kiểm tra secrets configuration
- Validate service layer imports
- Verify callable functions (read-only structure check)

### Release Candidate Tag

Current stable version: `release_candidate_v1`

- Commit: `49301aa57a07315a1f9af638e109f9b7a7ac8f78`
- Includes: Full service refactor, idempotency guards, dynamic prefix mapping
