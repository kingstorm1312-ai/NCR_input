## 1. Mục tiêu

Hệ thống NCR Mobile tồn tại để thay thế hoàn toàn quy trình lập và trình ký phiếu NCR bằng giấy.

Nhân viên có thể tạo phiếu NCR trực tiếp trên hệ thống, nhập thông tin lỗi, đính kèm hình ảnh, và gửi phiếu đi theo đúng luồng phê duyệt nội bộ mà không cần ký tay.

Hệ thống tự động luân chuyển phiếu NCR qua các cấp theo quy trình đã định, giúp:

- Ban giám đốc và các cấp quản lý theo dõi chính xác phiếu NCR đang bị kẹt ở đâu
- Có cái nhìn tổng quát về tình hình lỗi sản xuất trong toàn công ty
- Giao và theo dõi các nhiệm vụ khắc phục cho trưởng bộ phận ngay trên hệ thống
- Báo cáo và biểu đồ tổng hợp phục vụ giám sát NCR ở mức vận hành
  (xu hướng lỗi, top lỗi, phân bổ theo bộ phận, mức độ lỗi)

Hệ thống sử dụng tài khoản người dùng và mật khẩu để xác thực và thay thế chữ ký cá nhân trong toàn bộ quy trình.

## 2. In Scope

Hệ thống trong giai đoạn này phải hỗ trợ đầy đủ các chức năng sau:

- Tạo phiếu NCR trực tiếp trên hệ thống
- Upload hình ảnh lỗi kèm theo phiếu NCR
- Xuất phiếu NCR ra định dạng DOCX hoặc PDF để in ấn và lưu trữ khi cần
- Chuyển phiếu NCR tới cấp tiếp theo theo đúng quy trình đã quy định
- Thực hiện quy trình phê duyệt hoặc từ chối phiếu NCR theo flow nghiệp vụ
- Xem danh sách các phiếu NCR theo quyền người dùng
- Theo dõi các phiếu NCR đang bị kẹt, chưa được xử lý ở cấp nào để phục vụ việc đôn đốc, giám sát

## 3. Out of Scope

Trong giai đoạn hiện tại, hệ thống NCR Mobile KHÔNG bao gồm các nội dung sau:

- Phân tích thống kê nâng cao và BI chiến lược  
  (dashboard đa chiều phức tạp, drill-down sâu theo nhiều cấp, so sánh KPI theo mục tiêu năm, phân tích xu hướng dài hạn, dự báo lỗi)

- Tính KPI, chấm điểm hiệu suất cá nhân hoặc bộ phận để đánh giá nhân sự

- Tích hợp với các hệ thống bên ngoài như ERP, MES, HRM, WMS hoặc các hệ thống quản trị khác

- Chữ ký số pháp lý theo chuẩn pháp luật  
  (PKI, token ký số, ký điện tử có giá trị pháp lý)

- Mobile application native (Android / iOS)  
  Hệ thống chỉ hỗ trợ sử dụng trên nền web trong giai đoạn này

- Hệ thống thông báo real-time nâng cao  
  (push notification, email automation phức tạp, rule gửi thông báo tùy biến)

- Workflow phê duyệt tùy biến động bởi người dùng cuối  
  (tự tạo / sửa flow, thêm bớt cấp duyệt theo từng cá nhân)

- Hệ thống quản lý tài liệu độc lập ngoài phạm vi phiếu NCR  
  (Document Management System tổng quát)

- Phân quyền chi tiết ở mức hành động nhỏ  
  (ACL nâng cao, permission matrix phức tạp vượt ngoài role-based access hiện tại)

## 4. Invariants

- Phiếu NCR bị hủy (`da_huy`) không được xuất hiện trong bất kỳ báo cáo hoặc biểu đồ nào
- Người dùng chỉ được duyệt phiếu NCR đúng với vai trò của mình
- Phiếu NCR chỉ được chuyển trạng thái theo flow đã định
- Một phiếu NCR chỉ được tính một lần trong báo cáo
- Phiếu đã hoàn tất không được chỉnh sửa nội dung chính
