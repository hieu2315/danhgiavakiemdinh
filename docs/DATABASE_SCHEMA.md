# Thiết kế cơ sở dữ liệu ReLoop Market

## Kiến trúc và quy ước

- Database hiện tại là SQLite, giữ nguyên công nghệ của ứng dụng. Schema được nâng cấp bằng SQL migration tuần tự trong `database/migrations/`; seed catalog có tên/phiên bản trong `database/seeds/` và bảng `applied_seeds` để chạy lặp an toàn.
- Tiền VND lưu bằng `INTEGER` (đồng nguyên), không dùng `REAL` để tính giá, tổng, voucher, tiền thuê hay khoản cọc. `impact_factors.factor_value`, `impact_snapshots.factor_value` và `estimated_value` là `REAL` cho ước lượng phi tiền tệ; đây là số ước tính, không phải số tiền.
- Timestamp sự kiện là Unix epoch giây UTC (`INTEGER`). Ngày thuê là chuỗi ngày ISO `YYYY-MM-DD`, vì đó là ngày lịch địa phương. Khi hiển thị, đổi timestamp sang múi giờ người dùng; nhà cung cấp thanh toán có quy tắc múi giờ riêng.
- Giao dịch nhiều bảng dùng SQLite transaction, các luồng cạnh tranh như checkout/giữ lịch bắt đầu `BEGIN IMMEDIATE`. Tiền/tồn kho/đơn/giao dịch được tính và xác nhận backend.
- ID tự tăng là `INTEGER PRIMARY KEY`; mã sản phẩm/đơn/phiên hoặc mã provider là chuỗi có `PRIMARY KEY` hay unique constraint phù hợp.
- Hủy/ẩn/lưu trữ bằng trạng thái. Migration 011 ngăn xóa cứng đơn và các sổ lịch sử tài chính/điểm/tác động quan trọng; ghi nhận đảo điểm hoặc trạng thái mới thay vì sửa/xóa dấu vết.

## Nhóm bảng và quan hệ

| Nhóm | Bảng | Khóa/ràng buộc và mục đích |
|---|---|---|
| Tài khoản | `users` | PK số; email unique không phân biệt hoa thường; role bị CHECK giới hạn `customer/seller/admin`. Không có form công khai tạo admin. |
| Phiên | `sessions` | Hash token là PK, FK user; thời hạn có index. Cookie không lưu token thô trong bảng. |
| Hồ sơ/địa chỉ | `seller_profiles`, `addresses` | Một hồ sơ/người dùng; loại C2C/B2C và trạng thái CHECK. Địa chỉ thuộc user; xóa hồ sơ địa chỉ có thể cascade. |
| Danh mục | `categories` | Slug unique, `parent_id` tự tham chiếu RESTRICT, index cha/trạng thái/thứ tự; server chặn chu trình cây. |
| Sản phẩm | `products` | PK chuỗi, owner FK, giá INTEGER CHECK > 0, tồn kho và tồn kho thuê không âm, loại hàng/tình trạng/lifecycle CHECK, slug unique có điều kiện. `category_id` là FK; cột `category` text được giữ để tương thích dữ liệu/API cũ. |
| Tình trạng/ảnh | `product_condition_assessments`, `product_images` | Một phiếu tình trạng/sản phẩm, điểm và phần trăm CHECK; ảnh có FK, thứ tự, alt và unique `(product_id,image_path)`. |
| Kiểm duyệt sản phẩm | `product_history` | Snapshot JSON theo hành động, actor FK, index theo sản phẩm/thời gian. Lịch sử giữ kể cả khi sản phẩm lưu trữ. |
| Đơn hàng | `orders` | PK mã đơn, user FK, tổng INTEGER, trạng thái/phương thức/thời gian, bản snapshot địa chỉ, version điều kiện và thời điểm xác nhận. Không hard delete qua trigger. |
| Dòng đơn | `order_items` | FK order và product, snapshot tên/giá/số lượng tại thời điểm mua; quantity CHECK > 0. Index sản phẩm/đơn phục vụ báo cáo đơn người bán. Dòng đơn không bị xóa cứng. |
| Lịch sử đơn | `order_status_history` | Nhiều sự kiện cho một đơn, actor có thể null cho hệ thống, note và timestamp; append-only; index theo đơn/thời gian. |
| Thanh toán | `checkout_idempotency`, `payment_transactions`, `payment_status_history` | Unique `(user_id,idempotency_key)`, unique order trong bảng idempotency, unique mã tham chiếu provider; amount INTEGER; status CHECK; lịch sử callback giữ append-only. COD và VNPay cùng tham chiếu `orders`. |
| Đổi ưu đãi | `vouchers`, `voucher_redemptions` | Mã voucher unique không phân biệt hoa thường, loại/giá trị/thời hạn/giới hạn sử dụng; redemption FK voucher/user/order và unique order. Giá trị giảm INTEGER. |
| Đánh giá | `reviews` | Rating CHECK 1–5, trạng thái kiểm duyệt CHECK, unique `(order_id,product_id,user_id)`; product/status index. Chỉ review được duyệt mới dùng tính rating công khai. |
| Yêu thích | `favorites` | PK ghép `(user_id,product_id)` ngăn trùng; có thể cascade do đây không phải hồ sơ giao dịch. Giỏ hiện là bản nháp cục bộ client; checkout luôn tải lại giá/tồn kho và không tin cart client. |
| Điểm xanh | `points_ledger` | Sổ cái số nguyên, points khác 0, unique `(user_id,event_type,reference_type,reference_id)` chống ghi trùng; số dư tính từ ledger, reversal là sự kiện bù trừ; append-only. Voucher đổi từ điểm được lưu ở voucher/redemption. |
| Thuê/định kỳ | `rental_reservations`, `subscriptions` | Reservation gắn order/product/user, thời gian ISO, quantity và trạng thái CHECK, index lịch và user; subscription lưu chu kỳ/ngày hạn/trạng thái. Chưa tự thu subscription định kỳ. |
| Tác động | `impact_factors`, `impact_snapshots` | Hệ số có nguồn/phạm vi/version unique theo loại/version; snapshot trên dòng đơn giữ phiên bản hệ số đã dùng; snapshot append-only. |
| Email/thông báo | `notification_outbox` | Outbox trạng thái pending/sent/failed, FK user, index theo trạng thái và user/thời gian; minh bạch khi SMTP chưa gửi. |
| Bảo mật/quản trị | `audit_log`, `security_events`, `login_attempt_buckets`, `upload_assets` | Lưu sự kiện audit, sự kiện bảo mật đã hash, giới hạn đăng nhập và metadata upload; các index hỗ trợ tra cứu. Không lưu secret hoặc mật khẩu rõ. |
| Quyền dữ liệu | `privacy_requests` | FK user, loại/trạng thái CHECK, mô tả và ghi chú xử lý; index queue và chủ tài khoản. Đây là yêu cầu tiếp nhận, không tự động thực hiện xóa/truy xuất. |
| Hỗ trợ/khiếu nại | `support_requests` | FK user và order tùy chọn, loại/trạng thái CHECK, giới hạn tiêu đề/nội dung, ghi chú quản trị; index hàng đợi và chủ yêu cầu. Migration 013. |
| Phiên bản schema/seed | `schema_migrations`, `applied_seeds` | PK tên migration/seed và thời điểm áp dụng; tránh chạy lặp ngoài ý muốn. |

## Index trọng yếu

Index gốc và index bổ sung bao phủ sản phẩm theo trạng thái/danh mục/owner/slug; đơn theo user, trạng thái, hạn thanh toán; chi tiết theo order và product; lịch thuê; lịch sử trạng thái/thanh toán; review theo sản phẩm/trạng thái; voucher redemption; ledger điểm; outbox; audit theo entity; yêu cầu dữ liệu theo user/trạng thái. Dùng `EXPLAIN QUERY PLAN` và dữ liệu production trước khi thêm index khác để tránh index dư thừa.

## Quy tắc xóa và lưu giữ

- Đơn, chi tiết đơn, giao dịch thanh toán, lịch sử trạng thái, ledger điểm, voucher redemption và impact snapshot bị trigger chặn DELETE. Không có chức năng UI/API xóa các bản ghi này.
- FK mặc định RESTRICT/NO ACTION bảo vệ tài khoản/sản phẩm có giao dịch; cascade chỉ dùng cho dữ liệu phụ như session, yêu thích, ảnh/assessment khi chủ thể được xóa phù hợp.
- Trigger kỹ thuật không xác định thời hạn lưu theo luật. Trước vận hành thật, nhóm phải phê duyệt retention theo loại dữ liệu, nghĩa vụ lưu chứng từ và xử lý yêu cầu chủ thể; cần migration có quy trình nếu chính sách hợp pháp yêu cầu xóa/ẩn danh.
- Không có bảng `shipments` vì chưa tích hợp hãng vận chuyển/thực hiện tracking giao nhận; trạng thái giao hàng hiện được giữ trên đơn/lịch sử. Thêm bảng shipment khi có đơn vị, mã vận đơn, webhook và vòng đời bàn giao thật.
- Không có `roles`/`permissions` riêng vì đồ án hiện có ba role cố định kiểm tra bằng server middleware; chuyển sang RBAC động khi quyền quản trị cần cấu hình mà không đổi mã.
- Không có `carts` server-side vì cart chỉ là danh sách dự kiến của client; database order mới là dữ liệu chuẩn. Nếu cần đồng bộ nhiều thiết bị/khôi phục cart, thêm `carts`/`cart_items` với owner và expiry, nhưng vẫn phải tính lại giá/tồn kho lúc checkout.

## Migration 011 và 012

`011_transaction_retention_and_query_indexes.sql` thêm trigger append-only và index truy vấn bổ sung. `012_demo_data_labels.sql` thêm cờ `is_demo` cho orders/reviews và index để loại dữ liệu giả lập khỏi các thống kê giao dịch/rating thật. `init_db()` cũng backfill slug dễ đọc cho seed cũ sau khi seed chạy (slug unique có hậu tố ID khi cần); dữ liệu/đơn cũ không bị xóa hoặc viết lại. Chạy migration qua `python server.py`/`init_db()` sau backup; backup/restore hiện là thủ công theo `scripts/db_maintenance.py`.
## Dữ liệu demo (mục 15)

`python server.py` áp dụng migration và seed catalog an toàn. Trên Windows, `scripts/start-demo.ps1` chạy thêm `python scripts\seed_demo.py` trong môi trường development. Seed này idempotent và từ chối chạy khi `RELOOP_ENV=production`.

Tài khoản chỉ dành cho máy local:

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Khách hàng | `customer@reloop.local` | `CustomerDemo!2026` |
| Người bán cá nhân C2C | `seller.personal@reloop.local` | `SellerDemo!2026` |
| Người bán cửa hàng B2C | `seller.business@reloop.local` | `BusinessDemo!2026` |
| Quản trị viên | `admin@reloop.local` | `ReLoopAdmin-Local-2026!` (chỉ script local) |

Không dùng các credentials này trên máy chủ công khai. Tài khoản admin an toàn được khởi tạo qua `RELOOP_ADMIN_EMAIL` và `RELOOP_ADMIN_PASSWORD` ở môi trường backend trước lần khởi chạy đầu tiên; không có form đăng ký admin công khai.

Catalog gồm 24 sản phẩm, cây danh mục, voucher `DEMOXANH` còn hạn và `DEMOHETHAN` hết hạn, 4 đơn giả lập, 2 đánh giá mẫu, lịch sử điểm và hai gói ReBox mẫu. Đơn và đánh giá có cờ `is_demo`, được gắn nhãn trong các luồng giao dịch liên quan và không được tính vào doanh thu, điểm thật, rating SEO hay tác động môi trường. Hệ số môi trường seed là minh họa, inactive, không phải nguồn khoa học; trang tác động vẫn báo chưa cấu hình cho tới khi quản trị nhập hệ số đã xác minh.

Đơn mẫu, điểm, giao dịch VNPay hủy mẫu, đánh giá, subscriptions và hồ sơ seller đều là dữ liệu hư cấu cho trình diễn, không đại diện cho bán hàng, tiền thu hoặc tác động môi trường thực tế.
