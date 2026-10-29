# Báo cáo kết quả kiểm thử

Ngày rà soát: 29/10/2026  
Mã nguồn: gói ReLoopMarket-rental-fixed-tested  
Môi trường: Windows, Python 3.13.16, Node.js 24.22.0; SQLite tạm và HTTP loopback.

## Kết quả chạy

| Hạng mục | Kết quả |
|---|---|
| `python -m unittest discover -s tests -v` | **29 passed, 0 failed, 0 errors** — 7 helper/unit và 22 API integration |
| `node --check frontend/app.js` | Đạt |
| `python -m py_compile server.py backend/app.py tests/test_app.py scripts/db_maintenance.py` | Đạt |
| `git diff --check` | Không chạy: bản ZIP không có `.git` |

Các API test dùng cơ sở dữ liệu SQLite tạm, server loopback và dữ liệu test. Không dùng cơ sở dữ liệu production, không gọi VNPay thật và không gửi SMTP thật.

## Phạm vi đã chạy

Bộ test bao phủ helper, catalog/tìm kiếm/phân trang, đăng ký/đăng nhập/session, phân quyền admin cơ bản, checkout COD/idempotency, từ chối VNPay khi thiếu cấu hình, gợi ý sản phẩm, voucher với một số điều kiện về mức giảm/tối thiểu/hết hạn và lượt dùng, từ chối checkout vượt tồn kho, lịch thuê trùng/không trùng, cùng một luồng chuyển trạng thái đơn hợp lệ và một chuyển lùi bị từ chối.

Trong lần cập nhật gần nhất, 5 API test được bổ sung cho voucher, hạn mức tồn kho, lịch thuê và chuyển trạng thái đơn. Chi tiết nằm trong `tests/test_app.py`.

## Bằng chứng được nhóm cung cấp

Báo cáo giao diện ban đầu ghi nhận 19/19 ca thủ công đạt và kèm một số ảnh minh họa. Lượt rà soát này không chạy lại các ca đó; chúng được xem là kết quả do nhóm ghi nhận, không phải kết quả E2E độc lập đã tái lập.

## Giới hạn còn lại

Chưa đo line/branch coverage, chưa cấu hình CI, chưa chạy Selenium/Playwright, accessibility, kiểm thử tải hoặc pentest. Chưa kiểm tra giao dịch VNPay sandbox end-to-end hay SMTP thật. Suite chưa bao phủ đầy đủ ma trận role/ownership seller, toàn bộ trạng thái đơn và vòng đời thuê/hủy/hoàn, review, điểm xanh, CO₂, chấm điểm tình trạng và mọi quy tắc voucher. Kết quả hiện tại không đủ để kết luận kiểm định toàn diện hoặc sẵn sàng production.
