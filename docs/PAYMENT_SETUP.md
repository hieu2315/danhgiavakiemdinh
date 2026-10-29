# Thanh toán COD và VNPay Sandbox

## COD

Đơn COD khởi tạo `unpaid`. Người mua không thể đổi trạng thái thanh toán. Khi có căn cứ đối soát/thu tiền, admin dùng API quản trị với ghi chú tối thiểu; sự kiện payment status/audit được ghi lại. Không đánh dấu đã thanh toán chỉ vì đơn được hoàn tất giao hàng.

## QR nhận tiền cá nhân (đối soát thủ công)

Checkout có phương thức `VNPAY_QR` dùng mã QR do chủ dự án cung cấp tại `frontend/assets/vnpay-personal-qr.jpg`. Sau khi tạo đơn, website hiển thị ảnh QR, số tiền và mã đơn làm nội dung chuyển khoản. Đây là QR nhận tiền tĩnh: không tạo giao dịch VNPay, không gửi callback/IPN và không tự xác nhận người chuyển hay số tiền. Đơn giữ `unpaid` cho đến khi admin tự kiểm tra tiền đã vào tài khoản và chọn **Đối soát chuyển khoản QR** ở danh sách đơn; ghi chú đối soát được lưu trong lịch sử thanh toán và audit log. Không xác nhận chỉ dựa vào ảnh biên lai do người mua gửi.

## VNPay Sandbox

Backend chỉ tạo thanh toán khi `RELOOP_VNPAY_TMN_CODE`, `RELOOP_VNPAY_HASH_SECRET`, return URL và IPN URL được cấu hình. Secret chỉ ở môi trường server. Tham số được ký HMAC-SHA512 và IPN được xác minh trước cập nhật trạng thái; callback lặp idempotent. Return redirect chỉ tra trạng thái đã xác minh, không tự đặt paid. Expired/cancelled flow giải phóng tồn kho theo chính sách.

### Cấu hình trên Windows PowerShell

```powershell
$env:RELOOP_ENV = "development"
$env:RELOOP_VNPAY_TMN_CODE = "<sandbox merchant code>"
$env:RELOOP_VNPAY_HASH_SECRET = "<sandbox secret>"
$env:RELOOP_VNPAY_RETURN_URL = "https://<public-host>/api/payments/vnpay/return"
$env:RELOOP_VNPAY_IPN_URL = "https://<public-host>/api/payments/vnpay/ipn"
$env:RELOOP_VNPAY_PAY_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
$env:RELOOP_VNPAY_EXPIRE_MINUTES = "15"
```

Dùng dữ liệu sandbox do merchant portal/tài liệu chính thức cung cấp. Không dùng thẻ thật. IPN cần HTTPS public và phải được khai báo với merchant; localhost đơn thuần không nhận callback ngoài. Không commit credentials. Sau cấu hình, chạy order thử sandbox rồi xác minh callback chữ ký, số tiền, mã đơn, callback lặp, hủy và hết hạn ở database/audit.

## Trạng thái hiện tại

Credentials merchant và endpoint IPN public chưa được cung cấp, vì vậy chưa có giao dịch sandbox end-to-end. QR cá nhân chỉ hỗ trợ đối soát thủ công và không thay thế tích hợp merchant sandbox. Xem [TEST_REPORT.md](TEST_REPORT.md).
