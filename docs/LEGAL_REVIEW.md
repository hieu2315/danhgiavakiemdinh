# Rà soát căn cứ pháp lý — ReLoop Market

**Ngày rà soát nguồn:** 20/10/2026. **Phạm vi:** xác định các văn bản được nêu trong yêu cầu và một số văn bản hiện hành liên quan; đây không phải ý kiến tư vấn và không xác nhận sản phẩm đã tuân thủ.

## Kết quả đối chiếu sơ bộ

| Văn bản | Kết quả theo nguồn chính thức | Việc nhóm cần làm |
|---|---|---|
| Luật Giao dịch điện tử 20/2023/QH15 | Có hiệu lực 01/07/2024 | Rà soát bước đặt hàng, xác nhận, lưu vết phiên bản điều kiện và bằng chứng giao dịch. |
| Luật Bảo vệ quyền lợi người tiêu dùng 19/2023/QH15 | Có hiệu lực 01/07/2024; Nghị định 55/2024/NĐ-CP hướng dẫn cùng thời điểm | Xác định chủ thể chịu trách nhiệm, thông tin phải cung cấp, cơ chế khiếu nại/đổi trả và giao dịch từ xa. |
| Luật Thương mại điện tử 122/2025/QH15 | Có hiệu lực 01/07/2026 | Phân loại nền tảng và xác định nghĩa vụ của đơn vị vận hành, người bán C2C/B2C, hồ sơ và quy trình giao dịch. |
| Nghị định 248/2026/NĐ-CP | Văn bản quy định chi tiết Luật TMDT; có hiệu lực 01/07/2026 | Rà soát nghĩa vụ chi tiết, điều khoản chuyển tiếp và mối quan hệ hiệu lực với Nghị định 52/2013, 85/2021 trước khi vận hành. Tài liệu này chưa kết luận các nghị định cũ đã bị bãi bỏ toàn bộ. |
| Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 | Có hiệu lực 01/01/2026 | Rà soát căn cứ xử lý, quyền chủ thể, trách nhiệm, hồ sơ và quy trình sự cố theo hoạt động thực tế. |
| Nghị định 356/2025/NĐ-CP | Có hiệu lực 01/01/2026, quy định chi tiết Luật 91/2025 | Dùng cùng Luật 91/2025 để lập hồ sơ và quy trình. Điều khoản thi hành của nghị định quy định Nghị định 13/2023/NĐ-CP hết hiệu lực từ cùng ngày. |

Các văn bản khác có thể liên quan, gồm Luật Dữ liệu 60/2024/QH15 và quy định về thuế, hóa đơn, quảng cáo, sở hữu trí tuệ, thanh toán, an ninh mạng, lưu trữ kế toán, bảo vệ môi trường và hoạt động trung gian. Cần xác định theo mô hình pháp lý, dòng tiền và cách vận hành cuối cùng.

## Tài liệu chính thức

- [Luật Giao dịch điện tử 20/2023/QH15 — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=208421&pageid=27160&typegroupid=3)
- [Luật Bảo vệ quyền lợi người tiêu dùng 19/2023/QH15 — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=208363&pageid=27160)
- [Nghị định 55/2024/NĐ-CP — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?docid=210254&pageid=27160)
- [Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?docid=214590&pageid=27160)
- [Nghị định 356/2025/NĐ-CP — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=216387&pageid=27160)
- [Bản ký Nghị định 356/2025/NĐ-CP — Cổng văn bản Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/01/356-nd.signed.pdf)
- [Luật Thương mại điện tử 122/2025/QH15 — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=216503&pageid=27160&typegroupid=3)
- [Nghị định 248/2026/NĐ-CP — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?docid=218747&orggroupid=2&pageid=27160)
- [Nghị định 52/2013/NĐ-CP — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/?classid=1&docid=167457&pageid=27160)
- [Nghị định 85/2021/NĐ-CP — Cổng văn bản Chính phủ](https://vanban.chinhphu.vn/default.aspx?docid=204191&pageid=27160)
- [Thông tin triển khai Luật TMDT — Bộ Công Thương](https://moit.gov.vn/tin-tuc/ke-hoach-trien-khai-thi-hanh-luat-thuong-mai-dien-tu.html)

## Trạng thái triển khai trong source

- Trang `frontend/policies.html` chứa 12 mục chính sách/điều kiện và ghi rõ bản dự thảo, demo; không có tên pháp nhân, mã số thuế, địa chỉ hay liên hệ tự bịa.
- Các trường công khai cấu hình qua `RELOOP_OPERATOR_*`, `RELOOP_CONTACT_*`, `RELOOP_COMPLAINT_CHANNEL`, `RELOOP_PRIVACY_CONTACT`, `RELOOP_DATA_RETENTION_POLICY`; để trống thì UI hiện placeholder.
- Checkout yêu cầu xác nhận chủ động chưa đánh dấu sẵn; backend kiểm tra phiên bản và lưu `accepted_terms_version`, thời điểm máy chủ nhận đơn. Điều kiện thuê cũng lưu bản ghi.
- Yêu cầu dữ liệu được ghi nhận theo tài khoản và có hàng đợi admin. Đây mới là cơ chế tiếp nhận/theo dõi; thao tác truy xuất, chỉnh sửa, xóa hoặc phản đối phải được người có trách nhiệm thực hiện và xác minh trước khi đánh dấu hoàn tất.
- Giao hàng thật, trả/hoàn tiền, khiếu nại, hợp đồng cho thuê/đặt cọc, thu phí và quy trình tuân thủ dữ liệu đầy đủ chưa được triển khai. Không được coi trạng thái policy draft là cho phép mở bán thực tế.

## Việc cần hoàn tất trước nghiệm thu vận hành

1. Nhóm bổ sung thông tin chính xác của đơn vị vận hành và đầu mối hỗ trợ, người bán, quy trình tiếp nhận khiếu nại.
2. Chốt luồng hợp đồng, giao nhận, COD/đối soát, trả hàng/hoàn tiền, thuê/đặt cọc, voucher/điểm và chứng từ.
3. Lập sơ đồ dữ liệu, căn cứ và mục đích xử lý, thời hạn lưu từng loại, nhà cung cấp/địa điểm xử lý, phân quyền, yêu cầu chủ thể, sự cố và hồ sơ bắt buộc theo Luật 91/2025/NĐ 356/2025.
4. Đối chiếu điều khoản hiệu lực/chuyển tiếp Nghị định 248/2026 với Nghị định 52/2013 và 85/2021 từ toàn văn chính thức hiện hành; đánh giá nghĩa vụ thông báo/đăng ký và các yêu cầu riêng của nền tảng.
5. Nhờ giảng viên/đầu mối pháp lý duyệt chính sách theo đúng chủ thể, sản phẩm, luồng tiền và phạm vi hoạt động. Cập nhật `RELOOP_POLICY_VERSION` mỗi lần thay đổi nội dung áp dụng.
6. Chỉ đánh dấu yêu cầu dữ liệu “hoàn tất” sau khi đã xác minh danh tính, thực hiện tác vụ và ghi kết quả phù hợp; tuân thủ các ngoại lệ lưu giữ dữ liệu giao dịch.

