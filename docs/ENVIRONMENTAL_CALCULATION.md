# Tính tác động môi trường · phạm vi và giới hạn

## Quy tắc hiện tại

Sản phẩm/đơn được lưu ở SQLite. `impact_factors` giữ loại hàng, giá trị, đơn vị, scope, nguồn, URL, phiên bản và trạng thái active. Khi đơn hoàn tất, backend chụp hệ số có nguồn vào `impact_snapshots` theo order item để dữ liệu lịch sử không đổi khi hệ số mới được phát hành. Thống kê loại trừ đơn `is_demo=1`; không cộng trùng một order item. Khi không có hệ số đang hoạt động, API/UI trả `co2_kg: null` hoặc thông báo chưa cấu hình, không tự gán giá trị.

**Không có hệ số khoa học được xác minh seed sẵn.** Hai hệ số seed chỉ minh họa schema, `active=0`, nguồn ghi rõ không có căn cứ; chúng không dùng tính hoặc công bố impact.

## Cấu hình dữ liệu thật

Chỉ admin mới tạo phiên bản factor. Trước khi bật cần nhóm chọn phương pháp, đơn vị chức năng (ví dụ kg CO2e/sản phẩm), ranh giới vòng đời, nhóm hàng, giả định baseline, địa lý/thời gian, nguồn công khai có thể truy cập, phạm vi bất định và reviewer. Không so sánh đồ không tương thích. Tránh tuyên bố “đã tiết kiệm” nếu phương pháp chỉ cho một ước tính mô hình.

Sau khi nhập cần kiểm tra API admin, bản ghi factor/version/source, hoàn tất một đơn test trên staging và đối chiếu `impact_snapshots`/báo cáo. Không đưa số demo vào báo cáo thật. Thay factor không sửa snapshot giao dịch cũ.

## Phương pháp và nguồn

Hiện source code chỉ thực hiện phép nhân theo factor do admin đã xác minh; nó không cung cấp phương pháp LCA chuẩn, không suy ra phát thải tránh được từ riêng hành vi tái sử dụng, và chưa đính kèm nguồn hệ số thực trong seed. Nhóm phải bổ sung nguồn chuyên môn/EPD/LCA có scope phù hợp và rà soát độc lập trước khi công bố. Mọi số liệu trình diễn phải có nhãn “ước tính”, nêu factor/version, phạm vi, giả định và hạn chế.
