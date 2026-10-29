# Kịch bản marketing online — ReLoop Market

**Tài liệu giả định phục vụ đồ án. Không phải báo cáo chiến dịch đã chạy.** Ngân sách, KPI và đối tượng là giả định để lập kế hoạch; cần thẩm định bằng thử nghiệm nhỏ trước khi chi tiêu thật.

## Mục tiêu chiến dịch (thử nghiệm 4 tuần)

- Tăng lượt truy cập có ý định mua vào catalog và trang sản phẩm.
- Kiểm tra thông điệp nào khiến khách đọc kỹ tình trạng và xem chi tiết sản phẩm.
- Khuyến khích người bán đăng sản phẩm có ảnh/mô tả tình trạng đầy đủ.
- Đo đơn hàng hoàn tất và chi phí trên đơn; không tối ưu chỉ theo lượt nhấp.

## Đối tượng

1. Người 20–35 tuổi ở đô thị, quan tâm đồ gia dụng, nội thất, thời trang, thiết bị cũ và mua sắm tiết kiệm.
2. Người đang dọn nhà/chuyển trọ, có đồ còn dùng tốt muốn bán lại.
3. Nhóm cửa hàng nhỏ làm sản phẩm tái chế cần kênh giới thiệu sản phẩm.

Đây là phân khúc giả định để xây dựng bài tập; chưa dựa trên khảo sát người dùng hoặc dữ liệu khách hàng thực.

## Thông điệp và nội dung mẫu

**Thông điệp:** “Mua bán tuần hoàn – Tiêu dùng bền vững.” Xem rõ tình trạng, lựa chọn món đồ phù hợp, tiếp tục vòng đời sản phẩm. Không tuyên bố một giao dịch cụ thể đã giảm một lượng CO₂ nếu chưa có hệ số và phương pháp công bố.

**Mẫu tìm kiếm:** “Tìm món đồ còn giá trị sử dụng? Khám phá sản phẩm đã qua sử dụng và đồ tái chế trên ReLoop Market. Xem mô tả tình trạng và thông tin người bán trước khi chọn. Xem sản phẩm.”

**Mẫu mạng xã hội:** “Chiếc bàn, chiếc áo hay món đồ gia dụng vẫn còn dùng tốt? Hãy chụp rõ tình trạng, mô tả trung thực và cho món đồ cơ hội bước vào vòng đời tiếp theo. ReLoop Market — Mua bán tuần hoàn, tiêu dùng bền vững.”

**Mẫu hướng người bán:** “Dọn nhà và có món đồ còn tốt? Đăng ảnh thật, ghi rõ khuyết điểm và phụ kiện. Bắt đầu đăng bán trên ReLoop Market.”

Không dùng đánh giá, số lượng đơn, người bán nổi bật, chứng nhận xanh hoặc ưu đãi chưa có dữ liệu xác thực.

## Kênh, trang đích và ngân sách giả định

| Kênh | Vai trò | Ngân sách giả định / 4 tuần | Trang đích |
|---|---|---:|---|
| Google Search Ads | Nhu cầu có ý định tìm đồ cũ theo danh mục | 2.000.000đ | Trang danh mục/trang sản phẩm |
| Facebook/Instagram | Nội dung khám phá, bài hướng dẫn và thu hút người bán | 2.000.000đ | `frontend/guides.html` hoặc trang đăng bán |
| Sản xuất nội dung/ảnh mẫu | Ảnh minh họa sản phẩm và bài hướng dẫn | 1.000.000đ | `frontend/guides.html` |
| **Tổng giả định** | Chưa gồm VAT/phí nền tảng nếu phát sinh | **5.000.000đ** | — |

Đây là phân bổ minh họa, không phải báo giá, cam kết hiệu quả hoặc chi phí đã chi. Điều chỉnh theo báo giá thực tế và phê duyệt nhóm.

## KPI dự kiến (giả định để đặt ngưỡng thử nghiệm)

- 1.000–2.000 phiên truy cập có gắn UTM trong 4 tuần.
- Tỷ lệ vào trang sản phẩm từ landing page: mục tiêu ban đầu ít nhất 25%.
- Tỷ lệ bắt đầu checkout trên phiên đủ điều kiện: mục tiêu ban đầu 2–4%.
- Theo dõi số đơn tạo, tỷ lệ thanh toán/hoàn tất, hủy đơn và chi phí mỗi đơn hoàn tất; chưa đặt cam kết doanh thu vì chưa có baseline.
- Với quảng cáo tuyển người bán: theo dõi lượt bắt đầu hồ sơ, hồ sơ được duyệt và sản phẩm đạt chất lượng thông tin.

Đây là ngưỡng giả định đồ án. Đánh giá lại sau tuần đầu và không kết luận hiệu quả từ mẫu quá nhỏ.

## Đo lường

- Gắn UTM theo `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`; không đưa email, số điện thoại, mã đơn hoặc dữ liệu cá nhân vào URL.
- Khi được cấu hình công cụ analytics và thông báo quyền riêng tư phù hợp, theo dõi page view, xem sản phẩm, click CTA, bắt đầu checkout, đơn tạo và đơn hoàn tất bằng event tổng hợp.
- Đối chiếu nguồn traffic với đơn trong báo cáo nội bộ; dùng mã chiến dịch, không gửi thông tin đơn/khách cho nền tảng quảng cáo nếu chưa có căn cứ và cấu hình phù hợp.
- Ghi lại ngày, ngân sách thực chi, creative, lượt hiển thị, click, landing sessions, sản phẩm xem, checkout, đơn hoàn tất và hủy. Chưa có analytics/ads pixel trong source hiện tại.

## Lịch triển khai

- Tuần 1: kiểm tra landing pages, cấu hình analytics/consent nếu được duyệt, thử nội dung không trả phí.
- Tuần 2: chạy ngân sách nhỏ, kiểm tra truy vấn tìm kiếm và phản hồi chất lượng.
- Tuần 3: dừng mẫu gây nhầm lẫn, thử một biến thể thông điệp/ảnh.
- Tuần 4: tổng hợp hiệu quả theo đơn hoàn tất và chất lượng người bán; đề xuất tiếp tục/điều chỉnh/dừng.
