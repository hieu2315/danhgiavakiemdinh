# Bảo mật · ReLoop Market

## Đã triển khai

- Mật khẩu bcrypt cost 12; hash PBKDF2 cũ được rehash sau đăng nhập thành công. Thay mật khẩu cần mật khẩu hiện tại và thu hồi phiên khác.
- Phiên server-side qua cookie HttpOnly/SameSite, Secure theo cấu hình production; Origin/Referer guard với thao tác thay đổi dữ liệu. Production từ chối khởi động nếu `RELOOP_COOKIE_SECURE=1` chưa bật.
- Role và owner check ở API; đăng ký công khai chỉ tạo customer. Admin provision qua `RELOOP_ADMIN_EMAIL` / `RELOOP_ADMIN_PASSWORD` khi init.
- SQL tham số hóa, validate đầu vào backend, giới hạn đăng nhập sai, response sai credentials chung, security headers.
- Nội dung người dùng được escape khi render. Ảnh upload giới hạn PNG/JPEG/WebP, 3 MB/tệp, tối đa 5; MIME/chữ ký được kiểm tra, tên ngẫu nhiên và metadata gắn user.
- Audit các sự kiện thương mại/quản trị và security events; không ghi password/secret. Đơn, ledger, lịch sử payment, redemption và impact snapshot có retention/append-only guards.
- Secret ở biến môi trường, `.env`/backup/uploads bị ignore trong Git.

## Giới hạn và yêu cầu vận hành

Đây không phải chứng nhận bảo mật. Chưa có pentest độc lập, DAST/fuzzing, malware scanner, object storage, dependency monitoring, SIEM, MFA admin, email password reset, browser-level CSP/XSS test hoặc restore drill định kỳ. HTTP server tích hợp chỉ phục vụ demo/local; production cần HTTPS reverse proxy và WSGI/ASGI server, cookie Secure, CORS/origin được rà soát, rate/request limits và logging/retention phù hợp.

Không dùng mật khẩu demo hoặc dữ liệu demo ở public deployment. Không đặt secret trong frontend, log hoặc issue tracker. Backup chứa PII cần mã hóa/ACL và thời hạn lưu do đơn vị vận hành phê duyệt. Quy trình xóa/ẩn danh theo yêu cầu dữ liệu chưa tự động hóa; privacy request hiện là queue để nhân sự xử lý.

## Kiểm tra an toàn đã chạy

`tests/test_app.py` hiện kiểm tra password hashing helper, registration/login/session, customer bị từ chối tại API admin, checkout totals/idempotency, helper chữ ký VNPay và fail-closed khi thiếu credentials. Chưa có test trong suite hiện tại cho password change, CSRF/origin, login throttle, ownership, upload constraints hoặc payment callbacks. Xem [TEST_REPORT.md](TEST_REPORT.md).
