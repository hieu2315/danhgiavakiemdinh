# Kế hoạch kiểm thử và nghiệm thu

## Phạm vi và môi trường

Kiểm thử hiện có dùng SQLite tạm và HTTP loopback `127.0.0.1`; không dùng dữ liệu thật, không gọi cổng thanh toán hoặc email bên ngoài. Chạy suite trên Windows từ thư mục gốc dự án. Môi trường sandbox có thể cần quyền bind/connect loopback.

## Lệnh chạy

```powershell
python -m unittest discover -s tests -v
node --check frontend\app.js
python -m py_compile server.py backend\app.py tests\test_app.py scripts\db_maintenance.py
```

`unittest` đang được dùng; dự án hiện chưa cấu hình pytest, Coverage.py, Selenium/Playwright hoặc GitHub Actions. Test API không thay thế kiểm thử giao diện.

## Ma trận phạm vi

| ID | Kịch bản | Trạng thái trong suite hiện tại |
|---|---|---|
| T-UNIT | slug tiếng Việt, lọc văn bản, mật khẩu, chữ ký và thiếu cấu hình VNPay | Có (7 helper/unit tests) |
| T-CAT | danh sách sản phẩm, tìm kiếm và phân trang | Có |
| T-AUTH | đăng ký, mật khẩu yếu/trùng, đăng nhập đúng/sai, session và truy cập yêu cầu đăng nhập | Có (một phần; chưa có logout/đổi mật khẩu/rate-limit/CSRF) |
| T-ROLE | customer truy cập API admin | Có (chưa có seller ownership matrix) |
| T-ORDER | COD, tổng tiền, phí giao hàng, idempotency key và yêu cầu xác thực | Có (chưa kiểm tra biên tồn kho, voucher, hủy/hoàn) |
| T-VNPAY | checkout khi chưa cấu hình sandbox | Có (chỉ xác nhận fail-closed; không có chữ ký IPN hoặc giao dịch sandbox) |
| T-CO2 | công thức và nguồn hệ số tác động môi trường | Chưa có |
| T-CART | thao tác giỏ hàng trên UI | Chưa có browser test |
| T-STATE | chuyển trạng thái và quyền cập nhật vòng đời đơn | Chưa có |
| T-REVIEW / T-RENT / T-SUB | đánh giá, thuê và gói định kỳ | Chưa có |
| T-UI | responsive, keyboard, console, ảnh giao diện | Chưa có |
| T-COVERAGE / T-CI | line/branch coverage, pipeline tự động | Chưa cấu hình |

## Tiêu chí nghiệm thu

Ghi lệnh, ngày, môi trường và số pass/fail/skip vào `docs/TEST_REPORT.md`. Chỉ báo Pass cho kịch bản đã chạy. Khi mở rộng phạm vi, bổ sung test cho CO₂ và nguồn hệ số, voucher, biên tồn kho, trạng thái đơn, CSRF, seller ownership, VNPay callback, và E2E giao diện. Đặt ngưỡng coverage sau khi cấu hình công cụ và đo thực tế; không suy ra coverage từ số lượng test.
