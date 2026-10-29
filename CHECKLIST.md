# Checklist đối chiếu yêu cầu ReLoop Market

## Đã hoàn thành trong workspace

- [x] Đã phân tích toàn bộ source ban đầu: thư mục chỉ có Git, chưa có framework, backend, cấu hình package, database, API hay migration.
- [x] Giữ giao diện HTML/CSS/JS thuần hiện có; bổ sung backend Python và SQLite; dependency bcrypt được pin trong requirements.
- [x] Danh mục, tìm kiếm, lọc, sắp xếp, yêu thích và giỏ hàng; backend là nguồn dữ liệu sản phẩm đã duyệt.
- [x] Đăng ký/đăng nhập phía máy chủ với bcrypt cost 12, tự nâng PBKDF2 cũ sau đăng nhập hợp lệ, cookie phiên HttpOnly/SameSite, đổi mật khẩu có xác minh; tài khoản mới không thể tự đặt quyền admin.
- [x] Đặt hàng phía máy chủ tính lại giá; hỗ trợ COD và VNPay Sandbox có xác minh IPN; lưu đơn, lịch sử và trạng thái thanh toán.
- [x] Điểm xanh chỉ được xác nhận khi admin chuyển đơn sang Hoàn tất; đơn hoàn tất không thể quay về trạng thái khác.
- [x] Đăng bán với trạng thái chờ duyệt; API admin kiểm tra quyền trước khi duyệt/từ chối.
- [x] Backend phân quyền khách/người bán/quản trị; đăng ký chỉ tạo khách hàng, người bán nộp hồ sơ C2C/B2C và phải được quản trị duyệt trước khi đăng bán.
- [x] Người bán chỉ xem đơn có sản phẩm của mình và chỉ cập nhật tiến độ dòng đơn thuộc mình; API quản lý sản phẩm kiểm tra chủ sở hữu.
- [x] API khách hàng lưu địa chỉ, yêu thích; hủy đơn chỉ cho chủ đơn và trạng thái đang xử lý, đồng thời trả tồn kho.
- [x] API công khai chi tiết sản phẩm/hồ sơ người bán; quản trị có API duyệt hồ sơ, quản lý vai trò có điều kiện và nhật ký kiểm toán.
- [x] API tồn kho được kiểm tra khi tạo đơn và tự trừ khi đặt hàng.
- [x] Danh mục nhiều cấp có migration, seed cây danh mục và API quản trị thêm/sửa/ẩn/sắp xếp; backend từ chối chu trình cha/con.
- [x] API danh sách hỗ trợ tìm kiếm, lọc theo danh mục/giá/tình trạng/loại hàng/người bán/loại người bán/cho thuê, sắp xếp và phân trang; frontend nối tìm kiếm, lọc giá/tình trạng/loại/thuê và trang.
- [x] Trang chi tiết cơ bản tải dữ liệu thật từ API; số tác động trên trang chủ lấy từ đơn đã hoàn tất, không còn các số cộng đồng giả định.
- [x] Đơn có lịch sử trạng thái; API admin giới hạn chuyển trạng thái theo state machine, và giá frontend được đối chiếu với giá server trước khi tạo đơn.
- [x] Yêu cầu thuê chỉ với sản phẩm cho thuê, ngày và số ngày hợp lệ; lưu yêu cầu trong đơn hàng.
- [x] Ghi nhận gói subscription demo trong SQLite; không thu tiền định kỳ.
- [x] API tổng quan quản trị; giới hạn web server chỉ phục vụ ba asset frontend, không mở tệp database/source.
- [x] Giao diện quản trị có tab tài khoản/vai trò, seller, CRUD danh mục (ẩn thay vì xóa), queue hỗ trợ/khiếu nại và yêu cầu quyền dữ liệu; mọi mutation được backend kiểm tra admin và ghi audit.
- [x] Khách hàng gửi/xem yêu cầu hỗ trợ; API ràng buộc quyền sở hữu đơn, giới hạn nội dung/số yêu cầu đang chờ và có test quyền admin/customer.
- [x] Có bộ kiểm thử tích hợp API cho đăng nhập, vai trò, đơn hàng, điểm, kiểm duyệt, sandbox và sản phẩm không cho thuê.
- [x] Có cấu trúc frontend/backend/database/tests, migration SQL có version, seed catalog và script/tài khoản admin demo chỉ bind localhost.
- [x] Header có lối tắt yêu thích/đơn hàng/điểm/giỏ, menu mobile và tìm kiếm; footer có liên kết nội bộ tới điều khoản, dữ liệu cá nhân, đổi trả, giao hàng và FAQ demo.
- [x] Có trạng thái tải/lỗi/trống/thành công, focus bàn phím và xác nhận trước từ chối sản phẩm/hủy đơn; ảnh SVG theo danh mục có alt và ảnh dự phòng.
- [x] Mục 11: rate limit đăng nhập theo IP/tài khoản, thông báo lỗi chung, Origin/Referer guard khi có phiên cookie, security headers, bảo vệ quyền sở hữu upload, API security event chỉ dành admin, audit các sự kiện giao dịch quan trọng.
- [x] Mục 11: migration cho login buckets, security events và metadata upload; `.env.example` không có secret; `.gitignore` loại `.env`, backup và upload.
- [x] Mục 11: `scripts/db_maintenance.py` tạo backup SQLite nhất quán, verify `integrity_check` và restore có giữ bản database trước khi thay thế.

## Cần sửa/bổ sung trước nghiệm thu thực tế

- [x] Tích hợp VNPay Sandbox: URL thanh toán HMAC-SHA512, IPN kiểm tra chữ ký/mã merchant/số tiền, cập nhật idempotent, nhật ký payment, return redirect không tự xác nhận, hết hạn/hủy và giải phóng tồn kho. Credentials merchant và IPN HTTPS công khai chưa được cấp nên chưa phát sinh giao dịch sandbox thật.
- [ ] Nối UI khách hàng với API địa chỉ/yêu thích; bổ sung sửa địa chỉ, trang chi tiết sản phẩm/hồ sơ người bán, quản lý đơn người bán và màn quản trị tài khoản/vai trò.
- [ ] Hoàn thiện các khối riêng trên trang chủ (mới đăng, nổi bật/bán chạy, gợi ý, khuyến mại, người bán uy tín) dựa trên tiêu chí và giao dịch thật; hiện trang có catalog chung và mục cho thuê.
- [ ] Hoàn thiện bộ lọc nâng cao trong UI (danh mục con động, C2C/B2C, người bán, đánh giá), UI CRUD danh mục và so sánh sản phẩm. Thông số, ảnh, điểm tình trạng và chính sách đã có trong quản lý/chi tiết sản phẩm.
- [ ] Nối form checkout với danh sách địa chỉ và vận chuyển; thêm voucher/khuyến mại, tách đơn đa người bán hoặc thể hiện seller sub-orders trong UI. Backend hiện tính lại tổng, tồn kho và từ chối khi giá client đã cũ.
- [x] Thêm giới hạn đăng nhập sai và đổi mật khẩu có xác minh; khôi phục mật khẩu qua email và trang quản lý thông tin cá nhân/phiên còn thiếu.
- [ ] Thêm dữ liệu liên hệ nhận hàng riêng vào đơn, phí vận chuyển, hoàn tiền, xử lý khiếu nại và bảo vệ giao dịch C2C. Tồn kho cơ bản và hủy đơn đang xử lý đã có API.
- [ ] Hoàn thiện thuê: lịch khả dụng, tránh trùng lịch, ký quỹ thực thu/hoàn, xác nhận nhận-trả, hư hỏng và phí giao hàng.
- [ ] Hoàn thiện subscription: chu kỳ, thanh toán định kỳ, hủy/gia hạn, webhook, hóa đơn và thông báo.
- [ ] Bổ sung quét mã độc, giải mã/chuẩn hóa ảnh và object storage; hiện upload local chỉ nhận PNG/JPEG/WebP tối đa 3 MB và tối đa 5 ảnh, kiểm tra MIME/chữ ký, tên ngẫu nhiên và gắn quyền sở hữu.
- [ ] Xác minh email, đặt lại mật khẩu qua email, retention/giám sát bảo mật tập trung và audit dependency tự động (pip-audit chưa có sẵn trong môi trường này).
- [ ] Triển khai HTTPS với `RELOOP_COOKIE_SECURE=1`, reverse proxy/web server production, backup theo lịch và giám sát tập trung.
- [ ] Bổ sung chính sách/điều khoản/quyền riêng tư, quy trình khiếu nại, nội dung thông tin người bán, thuế/hóa đơn và rà soát pháp lý theo đơn vị triển khai.
- [ ] Hoàn thiện SEO kỹ thuật (sitemap, robots, canonical, metadata chia sẻ, dữ liệu cấu trúc) và số liệu môi trường dựa trên phương pháp/nguồn công khai được dẫn chứng. CO₂e chỉ được tính khi quản trị viên cấu hình hệ số có URL nguồn và phạm vi; mặc định không công bố giá trị.
- [ ] Thay máy chủ HTTP tích hợp bằng WSGI/ASGI server production sau reverse proxy HTTPS. Ứng dụng từ chối `RELOOP_ENV=production` nếu cookie không Secure.
- [ ] Chạy kiểm thử giao diện trên trình duyệt, responsive, accessibility và end-to-end trên máy dev/deployment; trình duyệt của phiên Codex đã chặn localhost/file nên chưa thực hiện được preview trực tiếp.

## Trạng thái bộ kiểm thử

- Lần chạy 29/10/2026: `python -m unittest discover -s tests -v` đạt 29/29 (7 helper/unit, 22 API). Phạm vi gồm helper, catalog, xác thực/session, phân quyền admin cơ bản, checkout COD/idempotency, fail-closed VNPay, gợi ý, một số điều kiện voucher, tồn kho, lịch thuê và một chuyển trạng thái đơn. Không suy rộng kết quả sang chức năng chưa có test.

## Chưa thể triển khai do thiếu thông tin xác thực bên ngoài

- Tài khoản/cửa hàng sandbox và credentials của cổng thanh toán được chọn; chưa được cung cấp.
- Tài khoản lưu trữ ảnh, email/SMS/OTP, bản đồ/vận chuyển và domain/hosting; chưa được cung cấp.
- Nội dung điều khoản, chính sách đổi trả/bảo hành/quyền riêng tư và cơ sở xác minh số liệu môi trường; chưa được cung cấp.

## 7.2 Chức năng nâng cao

- [x] Gợi ý theo quy tắc từ thuộc tính sản phẩm thật; không nhận là AI cá nhân hóa.
- [x] Đánh giá giới hạn theo đơn đã hoàn tất, kiểm tra duy nhất, làm sạch nội dung, hàng chờ kiểm duyệt và số sao tổng hợp.
- [x] Voucher %/số tiền có thời gian, đơn tối thiểu, trần giảm và giới hạn lượt; kiểm tra lại ở backend trong giao dịch đặt hàng.
- [x] Yêu thích lưu phía server cho tài khoản, xem/xóa/chuyển giỏ; khách chưa đăng nhập được yêu cầu xác thực.
- [x] SMTP adapter, mẫu email xác nhận/cập nhật đơn và outbox phân biệt pending/sent/failed. Cần credentials SMTP để gửi thư thật.
- [ ] Chưa có trang quản lý đánh giá phản hồi phía seller đầy đủ, so sánh sản phẩm, reset password email và xử lý toàn diện các thông báo cho thuê.


## 8. Nghiệp vụ thương mại tuần hoàn

- [x] Phiếu tình trạng sản phẩm có điểm ngoại quan, hoạt động, hao mòn, phụ kiện và thời gian sử dụng; backend tự tính điểm theo trọng số, không nhận điểm tổng từ client. Tỷ lệ vật liệu tái chế được lưu riêng; người bán tự khai, chưa phải kiểm định.
- [x] Sổ cái điểm xanh phía server; cấp điểm một lần cho đơn hoàn tất, ghi lịch sử và đổi điểm nguyên tử thành voucher dùng một lần, chặn số dư âm.
- [x] Thuê sản phẩm có đơn giá/ngày, tồn kho thuê riêng và kiểm tra giao nhau theo ngày trong transaction; hủy yêu cầu giải phóng lịch. Ký quỹ được ghi rõ là chưa cấu hình thu/hoàn.
- [x] Gói ReBox lưu chu kỳ tháng, ngày bắt đầu/ngày đến hạn, trạng thái và cho phép hủy; không tự thu tiền.
- [x] Quản trị cấu hình phiên bản hệ số tác động có đơn vị, phạm vi và URL HTTPS nguồn; lưu ảnh chụp hệ số theo dòng giao dịch hoàn tất. Khi chưa có hệ số, chỉ hiển thị số lượng, CO₂e báo chưa cấu hình.
- [ ] Chưa có nhiệm vụ xanh do quản trị cấu hình và luồng kiểm chứng/đổi thưởng cho từng nhiệm vụ.
- [ ] Chưa có luồng hoàn tiền; do đó chưa có nghiệp vụ đảo điểm thưởng sau hoàn tiền. Chưa có bàn giao/nhận trả/đánh giá hư hỏng cho thuê, cũng như tự tạo đơn chu kỳ subscription.


## 10. Thanh toán điện tử

- [x] COD ở trạng thái chưa thanh toán; thu COD cần căn cứ quản trị và được audit.
- [x] VNPay Sandbox module và xử lý IPN; thiếu credentials thì chặn tạo đơn, không giả lập thành công.
- [x] Khóa idempotency cho checkout, giao dịch/lịch sử trạng thái, callback lặp và quá hạn.
- [ ] Cấu hình TmnCode/HashSecret trên server, đăng ký IPN HTTPS công khai, chạy giao dịch thử theo tài liệu merchant.

## 9. Quản lý sản phẩm và người bán

- [x] Migration 007 bổ sung slug duy nhất, mô tả ngắn/đầy đủ, thông số JSON, loại người bán, chính sách, lifecycle status và updated_at; dữ liệu cũ được backfill theo trạng thái hiện hành.
- [x] Người bán tạo bản nháp hoặc gửi duyệt, xem sản phẩm của mình, cập nhật thông tin/giá/tồn kho/ảnh, ẩn, đăng lại, gửi duyệt lại hoặc lưu trữ. Server kiểm tra owner và không xóa cứng sản phẩm.
- [x] Duyệt/từ chối tại admin, yêu cầu lý do từ chối, lưu lịch sử snapshot cho tạo/sửa/chuyển trạng thái/kiểm duyệt; sửa sản phẩm đang bán sẽ trở về hàng chờ duyệt.
- [x] Tồn kho 0 tự chuyển sang hết hàng; sản phẩm hết hàng/ẩn không thể đặt mới, hủy đơn có thể khôi phục trạng thái bán nếu phù hợp. Giá và tồn kho được validate phía server.
- [x] Upload ảnh local có giới hạn loại/kích thước, tên file ngẫu nhiên, không nhận SVG/HTML; ảnh gắn alt text và dùng ảnh dự phòng khi hiển thị.
- [ ] Chưa có quét mã độc, object storage/CDN, quy trình quét mã độc/object storage và phân loại/khiếu nại vi phạm ngoài luồng từ chối có lý do.

## 12. Chính sách và quyền người tiêu dùng

- [x] Trang chính sách có đủ 12 mục: đơn vị vận hành, liên hệ, giao dịch chung, giao hàng, thanh toán, đổi trả/hoàn tiền, dữ liệu cá nhân, điều khoản, khiếu nại, người bán, thuê/đặt cọc và điểm thưởng.
- [x] Không tự bịa thông tin pháp nhân; trường trống cấu hình bằng biến môi trường và UI hiển thị placeholder.
- [x] Checkout yêu cầu rà soát hàng/giá/phí/thông tin nhận hàng/phương thức thanh toán và thao tác xác nhận chủ động; backend lưu version và thời điểm xác nhận theo đơn/thuê.
- [x] API ghi nhận yêu cầu dữ liệu cá nhân của user, giới hạn xem theo chủ tài khoản và admin, có trạng thái xử lý/audit.
- [x] Rà soát nguồn pháp lý chính thức ghi tại `docs/LEGAL_REVIEW.md` và trang chính sách; xác định luật mới có hiệu lực tại 2026.
- [ ] Chính sách đang ở trạng thái dự thảo. Nhóm cần bổ sung thông tin thật, nghĩa vụ nền tảng, quy trình giao nhận/hoàn tiền/khiếu nại và quy trình thực hiện yêu cầu dữ liệu; cần duyệt chuyên môn trước khi vận hành thật.

## 13. Marketing và SEO

- [x] Title/description riêng cho trang chủ, sản phẩm, chính sách, hướng dẫn và 404; URL sản phẩm `/p/<slug>`.
- [x] Product, Offer, BreadcrumbList JSON-LD render phía server theo dữ liệu đang hiển thị; không bịa review/rating/tồn kho; tình trạng hàng cũ được ghi rõ.
- [x] Sitemap động giới hạn trang công khai và sản phẩm đang bán; yêu cầu cấu hình origin HTTPS thật. robots.txt có quy tắc crawl, không được coi là phân quyền.
- [x] Có trang 404 noindex, nội dung hướng dẫn tuần hoàn và tài liệu chiến dịch quảng cáo giả định (ngân sách/KPI được đánh dấu giả định).
- [ ] Chưa cấu hình domain public/canonical production, Google Search Console, analytics/consent hay chạy quảng cáo thật; không tuyên bố đã có index hoặc hiệu quả chiến dịch.

## 14. Thiết kế cơ sở dữ liệu

- [x] Đã kiểm kê schema hiện hữu theo migration; giữ SQLite và kiến trúc, mô tả các bảng/quan hệ tại `docs/DATABASE_SCHEMA.md`.
- [x] Tiền VND dùng INTEGER; thời gian sự kiện lưu Unix epoch UTC, ngày thuê dùng ISO date; transaction checkout/thuê/thanh toán sử dụng `BEGIN IMMEDIATE`.
- [x] Migration 011 bổ sung index orders/payment/order items/audit/outbox/rental và trigger ngăn xóa cứng dữ liệu giao dịch/sổ lịch sử.
- [x] Bổ sung test migration, foreign key check, kiểu dữ liệu tiền và chính sách append-only.
- [ ] Chưa có bảng shipment vì chưa có carrier; chưa có cart server-side vì giỏ là bản nháp client; tài khoản/role đang là role enum cố định. Thiết kế hướng mở và giới hạn được ghi rõ trong tài liệu schema.

## Mục 15 · dữ liệu mẫu

- [x] Seed lặp an toàn có 24 sản phẩm, nhiều danh mục, seller C2C/B2C, sản phẩm cho thuê, voucher còn hạn/hết hạn và hệ số môi trường mẫu inactive, ghi rõ giả định.
- [x] Script local tạo customer, seller cá nhân, seller doanh nghiệp, admin cấu hình; 4 đơn đa trạng thái, review, ledger điểm và subscriptions demo. Có guard từ chối production.
- [x] Đơn và review mẫu có `is_demo`; thống kê giao dịch/rating/điểm và impact thật loại trừ dữ liệu demo. Không tính số liệu seed như giao dịch thật.
- [x] README và `docs/DATABASE_SCHEMA.md` nêu tài khoản demo, mật khẩu chỉ local và cách cấu hình admin riêng.

## 16. Kiểm thử và nghiệm thu

- [x] Chạy `python -m unittest discover -s tests -v`: 29/29 đạt (7 helper/unit, 22 API integration). Chi tiết và giới hạn theo từng luồng nằm trong `docs/TEST_REPORT.md` và `tests/test_app.py`.
- [x] Kiểm tra cú pháp JavaScript bằng `node --check frontend/app.js` và Python bằng `python -m py_compile server.py backend/app.py tests/test_app.py scripts/db_maintenance.py`. `git diff --check` không chạy vì ZIP không có `.git`.
- [ ] Kiểm thử VNPay sandbox end-to-end chưa thực hiện vì chưa có credentials merchant và IPN HTTPS public; suite hiện chỉ kiểm tra helper chữ ký và từ chối khi thiếu cấu hình; chưa test callback/IPN hoặc giao dịch cổng ngoài.
- [ ] Chưa chạy Playwright/browser UI, ma trận desktop/mobile, accessibility, console hoặc kiểm tra link trong trình duyệt; chưa có cấu hình e2e trong dự án.
- [ ] Chưa có test bao phủ riêng hoàn tiền/đảo điểm, chu kỳ subscription tự thu, cập nhật trả thuê hoặc browser-level CSRF/XSS; các nghiệp vụ này chưa được triển khai đầy đủ hoặc cần kiểm tra bổ sung trước nghiệm thu vận hành.

## Tiến độ theo giai đoạn thực hiện

| Giai đoạn | Trạng thái hiện tại | Bằng chứng / phần còn lại |
|---|---|---|
| 1. Kiểm tra source | Hoàn thành | Kiến trúc Python/SQLite/HTML-CSS-JS, API, migration và tests được rà soát; checklist từng mã tại `docs/FEATURE_CHECKLIST.md`. |
| 2. Nền tảng | Hoàn thành | Migration/seed, auth/role và demo; integration tests. |
| 3. Giao diện | Một phần | Các trang/chức năng hiện có; chưa xác minh bằng browser, responsive/keyboard; một số filter và seller/account UI còn thiếu. |
| 4. Mua hàng | Một phần | Backend checkout/order/voucher/idempotency có tests; address shipping/seller sub-order UI còn thiếu. |
| 5. Thanh toán | Một phần | COD và nội bộ VNPay IPN tests; merchant credentials/public callback chưa có. |
| 6. Chức năng nâng cao | Một phần | Gợi ý/review/favorites/voucher/email outbox; chưa có so sánh và đầy đủ seller review reply/reset email. |
| 7. Tuần hoàn | Một phần | Điểm/thuê/subscription cơ bản có tests; refund/return/cycles và impact sources thật còn thiếu. |
| 8. Bảo mật/pháp lý/SEO | Một phần | Baseline security, policies draft, metadata/sitemap; cần vận hành thật, rà soát pháp lý và factor nguồn. |
| 9. Kiểm thử | Một phần | 29/29 test pass (7 helper/unit + 22 API); browser E2E, visual/accessibility, coverage và external sandbox chưa chạy. |
| 10. Bàn giao | Hoàn thành ở mức đồ án/local | README, env example, feature/test/security/payment/DB/legal/environment docs, migration/seed/backup; production items vẫn mở. |
