# SYSTEM DOCUMENTATION & DATA FLOW

## 1. Overview

Hệ thống **NCR Mobile** quản lý quy trình tạo, phê duyệt và xử lý các phiếu NCR (Non-Conformance Report) trong nhà máy. Hệ thống sử dụng **Streamlit** (Frontend) và **Google Sheets** (Backend/Database).

## 2. Data Schema (Google Sheets)

Dữ liệu chính nằm trong sheet `NCR_DATA`.
Mỗi dòng đại diện cho một **Lỗi** (Error Row). Một phiếu NCR (`so_phieu_ncr`) có thể bao gồm nhiều dòng lỗi.

### Key Columns

- `so_phieu_ncr`: Mã định danh phiếu (Primary Key cho nhóm lỗi).
- `trang_thai`: Trạng thái hiện tại của phiếu.
- `kp_status`, `kp_assigned_to`: Theo dõi hành động khắc phục (Corrective Action).

## 3. Workflow & Status Lifecycle

### A. Quy trình Phê duyệt Chuẩn (Happy Path)

1. **Draft (`draft`)**: Nhân viên tạo phiếu (hoặc bị trả về).
2. **Chờ Trưởng Ca (`cho_truong_ca`)**: Trưởng ca duyệt sơ bộ.
3. **Chờ Trưởng BP (`cho_truong_bp`)**: Trưởng bộ phận duyệt.
4. **Chờ QC Manager (`cho_qc_manager`)**: QC Manager đánh giá, phân loại lỗi.
5. **Chờ Giám Đốc (`cho_giam_doc`)**: Giám đốc phê duyệt phương án xử lý.
6. **Chờ BGĐ Tân Phú (`cho_bgd_tan_phu`)**: (Tùy chọn) Cấp cao nhất duyệt.
7. **Hoàn thành (`hoan_thanh`)**: Quy trình kết thúc.

### B. Quy trình Từ Chối (Rejection)

Nếu bất kỳ cấp nào từ chối, phiếu sẽ quay về trạng thái **`draft`** để người tạo chỉnh sửa và gửi lại.

### C. Quy trình Hủy Phiếu (Cancellation)

- **Trạng thái:** `da_huy`
- **Trigger:** Nhân viên bấm "Hủy phiếu" khi phiếu đang ở trạng thái `draft`.
- **Logic:**
  - Dữ liệu **KHÔNG** bị xóa khỏi Sheet.
  - Cột `trang_thai` được cập nhật thành `da_huy`.
  - **Critical Rule:** Các phiếu `da_huy` phải bị **LOẠI BỎ HOÀN TOÀN** khỏi các báo cáo thống kê, biểu đồ và KPI. Xem như phiếu này chưa từng tồn tại về mặt sản xuất.

## 4. Sub-Process: Corrective Action (Hành động khắc phục)

QC Manager hoặc Director có thể giao task khắc phục cho bộ phận khác:

- Trạng thái phiếu chuyển sang: `khac_phuc_[ROLE_NGUOI_NHAN]`.
- Phiếu tạm thời rời khỏi luồng phê duyệt chính.
- Sau khi khắc phục xong -> Được xác nhận -> Quay lại luồng phê duyệt.

## 5. Reporting Rules (Dành cho AI Agents)

Khi thực hiện query hoặc tạo báo cáo từ `NCR_DATA`:

1. **Luôn filter loại bỏ `da_huy`**:

   ```python
   df = df[df['trang_thai'] != 'da_huy']
   ```

2. **Đếm số lượng phiếu:** Phải group by `so_phieu_ncr` trước khi đếm (vì 1 phiếu có nhiều dòng).
3. **Hierarchy:** `bo_phan` (Bộ phận chính) -> Prefix mã phiếu (Khâu/Chuyền chi tiết).
