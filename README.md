# ReLoop Market

Website thương mại điện tử tuần hoàn C2C/B2C. Frontend HTML/CSS/JavaScript, backend Python và SQLite, migration SQL có phiên bản. Yêu cầu Python 3.10+.

## Chạy trên Windows PowerShell

```powershell
py -m pip install -r requirements.txt
.\scripts\start-demo.ps1
```

Mở `http://127.0.0.1:8000`. Script demo tạo hoặc cập nhật database local `reloop.sqlite3` trong thư mục dự án, rồi thêm dữ liệu mẫu an toàn theo cơ chế idempotent. Tài khoản quản trị local:

- Email: `admin@example.test`
- Mật khẩu: `AdminPassword-123`

Chỉ dùng tài khoản này trên máy local. Khi triển khai, đặt `RELOOP_ADMIN_EMAIL` và `RELOOP_ADMIN_PASSWORD` trước lần khởi chạy đầu tiên. Người đăng ký công khai luôn nhận vai trò khách hàng.

Sao chép `.env.example` làm danh sách tham khảo; đặt giá trị bằng môi trường máy chủ. Không commit `.env`. `RELOOP_ENV=production` yêu cầu `RELOOP_COOKIE_SECURE=1`; cần HTTPS qua reverse proxy. HTTP server tích hợp chỉ dành cho local/demo, chưa phải server production.

## Tính năng

- Tìm kiếm, lọc, sắp xếp, phân trang; trang chi tiết sản phẩm, yêu thích, giỏ hàng và checkout.
- Khách, seller và admin; kiểm tra vai trò và quyền sở hữu ở backend.
- Bán sản phẩm cũ/tái chế, duyệt sản phẩm và hồ sơ người bán; quản lý tồn kho, thuê, đơn và review.
- COD, VNPay Sandbox và chuyển khoản QR cá nhân đối soát thủ công. Sandbox chỉ được xác nhận sau IPN có chữ ký hợp lệ. QR cá nhân giữ đơn chưa thanh toán đến khi admin kiểm tra tiền vào tài khoản và ghi nhận; QR không có callback tự động.
- Phí giao hàng lấy khối lượng sản phẩm do người bán khai báo: đơn tổng từ 3 kg miễn phí, dưới 3 kg thu 30.000đ. Phí và khối lượng được tính/chụp ở backend lúc tạo đơn; voucher chỉ giảm phần hàng.
- Điểm xanh, voucher, review kiểm duyệt và tác động môi trường chỉ khi có hệ số được cấu hình.
- Gợi ý sản phẩm dùng luật kết hợp (nội dung, mua cùng, bán hàng/review và dữ liệu favorite/đơn của chính tài khoản), không phải AI/ML.
- Trang chủ, trang chi tiết và giỏ hàng có các dải gợi ý; khách xem xu hướng phổ biến, tài khoản đã đăng nhập được cá nhân hóa.
- API tương thích `/api/recommendations/{product_id}` và bổ sung `/api/recommendations?context=home|cart&limit=N&cart=id1,id2`.
- Email outbox; trạng thái pending/failed được giữ nếu SMTP chưa gửi được.

Giỏ hàng phía trình duyệt được lưu cục bộ; dữ liệu tài khoản, sản phẩm, đơn hàng, điểm, giao dịch và phân quyền nằm ở SQLite/backend.

## Bảo mật 

- Mật khẩu dùng bcrypt cost 12; hash PBKDF2 cũ được nâng sau lần đăng nhập thành công. Đổi mật khẩu xác minh mật khẩu hiện tại và thu hồi các phiên khác.
- Throttle đăng nhập theo IP và tài khoản, thông báo sai chung, cookie HttpOnly/SameSite, kiểm tra Origin/Referer cho thao tác có cookie, security headers.
- Dùng SQL tham số hóa, kiểm tra quyền phía server, escape nội dung khi hiển thị và giới hạn upload ảnh PNG/JPEG/WebP tối đa 3 MB. Tệp mới ở `storage/uploads/`, ngoài web root, tên ngẫu nhiên, metadata gắn với người tải lên.
- Audit log ghi sự kiện quản trị, đơn hàng, điểm và callback; trang sự kiện bảo mật yêu cầu admin. Không ghi mật khẩu hay secret.
- `.env.example` không có credentials thật. `.gitignore` loại `.env`, backup và ảnh upload.

### Backup và restore SQLite

Backup là thao tác thủ công; script không lập lịch tự động. Nên chọn `RELOOP_BACKUP_DIR` ở vị trí được kiểm soát quyền truy cập:

```powershell
py scripts\db_maintenance.py backup
py scripts\db_maintenance.py verify .\backups\reloop-YYYYMMDD-HHMMSS.sqlite3
py scripts\db_maintenance.py restore .\backups\reloop-YYYYMMDD-HHMMSS.sqlite3
```

`backup` dùng SQLite online backup và kiểm tra integrity. Luôn chạy `verify` trước khi restore; dừng ứng dụng trước restore. Database hiện tại được giữ ở tệp `.before-restore` cạnh database đích. Bảo vệ bản backup như dữ liệu người dùng.

## Chạy kiểm thử và kiểm tra mã

```powershell
py -m unittest discover -s tests -v
node --check frontend\app.js
py -m py_compile server.py backend\app.py tests\test_app.py scripts\db_maintenance.py
```

Bộ kiểm thử gồm **29 tests passed, 0 failed** (7 helper/unit và 22 API integration). Bộ test dùng SQLite tạm và HTTP loopback; phạm vi gồm helper, catalog, tài khoản/session, phân quyền cơ bản, checkout/idempotency, VNPay fail-closed, gợi ý sản phẩm, một số điều kiện voucher, tồn kho, đặt thuê trùng lịch và chuyển trạng thái đơn. Selenium/Playwright, coverage, CI, VNPay thật và SMTP thật chưa được kiểm tra. Xem [báo cáo kết quả](docs/TEST_REPORT.md) để biết phạm vi và giới hạn.

## VNPay Sandbox

Đặt credentials sandbox ở môi trường backend, không đưa vào frontend, Git hoặc log:

```powershell
$env:RELOOP_VNPAY_TMN_CODE = "Mã merchant sandbox"
$env:RELOOP_VNPAY_HASH_SECRET = "Secret sandbox"
$env:RELOOP_VNPAY_RETURN_URL = "https://ten-mien/api/payments/vnpay/return"
$env:RELOOP_VNPAY_IPN_URL = "https://ten-mien/api/payments/vnpay/ipn"
$env:RELOOP_VNPAY_PAY_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
$env:RELOOP_VNPAY_EXPIRE_MINUTES = "15"
```

IPN cần được cấu hình tại merchant và truy cập được qua HTTPS; localhost không nhận callback công khai. Return URL chỉ hiển thị trạng thái xác minh; trạng thái thanh toán do backend cập nhật sau IPN. Chỉ dùng dữ liệu sandbox.

## Cấu trúc

- `frontend/`: giao diện và assets.
- `backend/`: API, xác thực, nghiệp vụ, email.
- `database/migrations/`: schema SQL có version; `database/seeds/`: catalog demo.
- `scripts/db_maintenance.py`: backup, verify và restore thủ công.
- `tests/`: integration tests.
- `requirements.txt`: dependency backend đã pin.

## Giới hạn triển khai

Không dùng làm dịch vụ production trước khi có HTTPS/reverse proxy và web server production, audit dependencies định kỳ, backup theo lịch và nơi lưu ngoài máy, giám sát/retention log, xác minh và khôi phục tài khoản, xử lý hoàn tiền/khiếu nại, quét/chuẩn hóa ảnh, rà soát pháp lý và kiểm thử UI/e2e. `pip-audit` chưa được cài nên chưa có báo cáo dependency audit tự động. Giao dịch VNPay thật cần credentials sandbox và IPN HTTPS; hệ số môi trường cần nguồn và phạm vi được xác minh.

## Chính sách, dữ liệu cá nhân và rà soát pháp lý

Mở `policies.html` để xem thông tin đơn vị vận hành, liên hệ và 12 nhóm điều kiện/chính sách. Các trường chưa được nhóm xác minh để trống trong `.env.example`; đặt biến `RELOOP_OPERATOR_*`, `RELOOP_CONTACT_*`, `RELOOP_COMPLAINT_CHANNEL`, `RELOOP_PRIVACY_CONTACT`, `RELOOP_DATA_RETENTION_POLICY` trong môi trường backend. Không điền dữ liệu giả. Yêu cầu quyền dữ liệu hiện được tiếp nhận và theo dõi; việc truy xuất/chỉnh sửa/xóa thực tế cần người xử lý xác minh và hoàn thành thủ công trước khi đóng yêu cầu.

Rà soát văn bản, nguồn chính thức và các việc còn lại ở `docs/LEGAL_REVIEW.md`. Tại ngày 20/10/2026, cần tính đến Luật Thương mại điện tử 122/2025/QH15 và Nghị định 248/2026/NĐ-CP (hiệu lực 01/07/2026), cùng Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP (hiệu lực 01/01/2026). Đây không phải xác nhận tuân thủ; chưa bật bán thật trước khi xác minh thông tin đơn vị vận hành, nghĩa vụ nền tảng và các chính sách vận hành thực tế.

## SEO và marketing 

- Trang sản phẩm công khai được server render tại `/p/<slug>` với title/description riêng, canonical tuyệt đối khi `RELOOP_PUBLIC_BASE_URL` được cấu hình HTTPS, breadcrumb và JSON-LD Product/Offer/BreadcrumbList lấy từ dữ liệu sản phẩm đang bán. Rating chỉ có trong JSON-LD khi tồn tại đánh giá đã duyệt.
- Sitemap XML động chỉ hoạt động sau khi đặt `RELOOP_PUBLIC_BASE_URL` thành origin HTTPS thật. Sitemap chỉ chứa trang công khai và sản phẩm còn bán; `/robots.txt` hướng dẫn bot nhưng không thay thế backend authorization.
- Nội dung hướng dẫn ở `frontend/guides.html`; kịch bản chiến dịch giả định ở `docs/MARKETING_PLAN.md`. Chưa có analytics hoặc chiến dịch quảng cáo chạy thật.

## Thiết kế cơ sở dữ liệu 

Schema SQLite, quan hệ, khóa, index, kiểu tiền, thời gian, transaction, retention và các nhóm dữ liệu đã triển khai được mô tả trong `docs/DATABASE_SCHEMA.md`. Migration 014 lưu khối lượng theo gram và snapshot phí/khối lượng giao hàng trên từng đơn. Tiền dùng số nguyên VND; hệ số tác động là ước lượng phi tiền tệ. Cart hiện là dữ liệu nháp tại trình duyệt, còn checkout xác thực lại bằng backend.
## Dữ liệu và tài khoản demo 

`scripts/start-demo.ps1` khởi tạo catalog gồm 24 sản phẩm rồi tạo giao dịch demo cục bộ. Tài khoản mẫu chỉ dùng trên máy local:

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Khách hàng | `phamvanhieu2315@gmail.com` | `hieu23012005` |
| Người bán cá nhân C2C | `hieuchung@gmail.com` | `hieuchung123456` |
| Người bán cửa hàng B2C | `hieuchung@gmail.com` | `hieuchung123456` |
| Quản trị viên local | `admin@example.test` | `AdminPassword-123` |

Không dùng các mật khẩu demo trên deployment công khai. Khi cần tạo admin riêng, thiết lập `RELOOP_ADMIN_EMAIL` và `RELOOP_ADMIN_PASSWORD` trong môi trường backend trước lần khởi chạy đầu tiên. `python scripts/seed_demo.py` chạy lại seed giao dịch demo theo cách idempotent và từ chối khi `RELOOP_ENV=production`.

Đơn, thanh toán, đánh giá, điểm và subscriptions seed là hư cấu; được gắn cờ demo và loại khỏi thống kê giao dịch/rating/tác động thực. Các hệ số môi trường mẫu inactive, không dùng tính tác động. Chi tiết tại `docs/DATABASE_SCHEMA.md`.

## Tài liệu bàn giao

- [Checklist chức năng theo từng mã yêu cầu](docs/FEATURE_CHECKLIST.md)
- [Kế hoạch kiểm thử](docs/TEST_PLAN.md) và [báo cáo kiểm thử thực tế](docs/TEST_REPORT.md)
- [Cơ sở dữ liệu](docs/DATABASE.md) · [schema chi tiết](docs/DATABASE_SCHEMA.md)
- [Bảo mật và giới hạn](docs/SECURITY.md)
- [Cấu hình thanh toán COD/VNPay](docs/PAYMENT_SETUP.md)
- [Phương pháp và giới hạn ước tính môi trường](docs/ENVIRONMENTAL_CALCULATION.md)
- [Rà soát pháp lý](docs/LEGAL_REVIEW.md) · [kế hoạch marketing](docs/MARKETING_PLAN.md)
- Migrations: `database/migrations/`; seeds: `database/seeds/`; backup/verify/restore: `scripts/db_maintenance.py`.

Không thêm Docker Compose vì ứng dụng hiện là Python + SQLite không cần dịch vụ database riêng; `scripts/start-demo.ps1` là cách chạy local trên Windows. README và checklist ghi riêng những phần chưa triển khai hoặc chưa thể xác minh.

