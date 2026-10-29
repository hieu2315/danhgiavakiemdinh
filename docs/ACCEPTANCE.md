# ReLoop Market · tiêu chí chấp nhận cuối cùng

Ngày rà soát: 29/10/2026. **Đạt API** chỉ mô tả hành vi đã có test tương ứng; **Một phần** nghĩa là mới kiểm tra một phần luồng; **Chưa kiểm thử** nghĩa là có mã nguồn nhưng suite hiện tại chưa xác nhận; **Bị chặn** phụ thuộc môi trường hoặc credentials. Không kết luận nghiệm thu toàn bộ từ số test pass.

| # | Tiêu chí | Trạng thái | Bằng chứng hiện có | Phần còn lại |
|---:|---|---|---|---|
| 1 | Trang chủ hoạt động | Một phần | Có HTML/JS và dữ liệu catalog API | Chưa chạy browser smoke/E2E trong lượt này. |
| 2 | Danh mục sản phẩm nhiều cấp | Chưa kiểm thử | API và migrations có trong source | Chưa có test category trong suite hiện tại. |
| 3 | Trang chi tiết sản phẩm | Đạt API một phần | API-15 kiểm tra HTTP trang sản phẩm và script gợi ý | Chưa nghiệm thu render tương tác trên trình duyệt. |
| 4 | Tìm kiếm và phân trang | Đạt API một phần | API-02 tìm kiếm và phân trang | Chưa bao phủ hết bộ lọc và giao diện. |
| 5 | Giỏ hàng hoạt động | Một phần | Client cart và checkout server-side | Chưa có browser E2E hoặc đồng bộ đa thiết bị. |
| 6 | Đăng ký, đăng nhập và session | Đạt API một phần | API-03–07 kiểm tra đăng ký, mật khẩu yếu/trùng, đăng nhập và yêu cầu xác thực | Chưa test logout, đổi mật khẩu, rate limit hoặc UI. |
| 7 | Đặt hàng và trạng thái | Đạt API một phần | API-09–11, API-20 và API-22 | COD/idempotency, vượt tồn kho và một chuyển trạng thái được kiểm tra; chưa test toàn bộ state graph/cancel/refund. |
| 8 | Quản trị | Một phần | API-08 xác nhận customer bị từ chối tại API admin | Chưa test CRUD admin, seller ownership hoặc browser UI. |
| 9 | Chức năng nâng cao | Một phần | API-13–17 gợi ý; API-18–19 voucher | Review/favorites UI và toàn bộ quy tắc voucher chưa nghiệm thu. |
| 10 | COD | Đạt API một phần | API-10 tạo COD, tổng tiền và idempotency | Thu tiền và đối soát thực tế chưa cấu hình. |
| 11 | VNPay sandbox | Bị chặn một phần | UT-05/06 chữ ký helper; API-12 từ chối khi thiếu credentials | Chưa test IPN callback hoặc giao dịch sandbox. |
| 12 | Mật khẩu và phân quyền | Đạt API một phần | Helper hash; API-08 customer bị từ chối API admin | Chưa có ma trận role/ownership đầy đủ. |
| 13 | SQLi, XSS, CSRF | Chưa kiểm thử bảo mật chuyên biệt | Có biện pháp trong source | Chưa có fuzzing, browser security test hoặc pentest. |
| 14 | Rate limit và upload | Chưa kiểm thử | Handler có trong source | Suite hiện tại không có test riêng; chưa malware scan. |
| 15 | Nhật ký giao dịch | Chưa kiểm thử | Audit/history tables và handlers có trong source | Chưa có assertion test cho history/audit hoặc retention. |
| 16 | Backup/restore | Chưa kiểm thử trong lượt này | Script và tài liệu có trong source | Chưa diễn tập restore định kỳ. |
| 17 | Hồ sơ seller và chính sách | Một phần | API/policy draft có trong source | Chưa điền thông tin pháp nhân thật hoặc duyệt pháp lý. |
| 18 | Xác nhận điều kiện đặt hàng | Đạt API một phần | Checkout test dùng terms version hiện hành | Chưa nghiệm thu giao diện trình duyệt. |
| 19 | SEO/sitemap/robots | Một phần | API-15 kiểm tra trang sản phẩm và script | Chưa có test crawler/sitemap/deployment. |
| 20 | Marketing/quảng cáo | Chưa chạy | Tài liệu kế hoạch | Chưa chạy chiến dịch thật. |
| 21 | Chấm điểm tình trạng | Chưa kiểm thử | API có trong source | Chưa xác nhận công thức hoặc dữ liệu đầu vào. |
| 22 | Điểm xanh | Chưa kiểm thử | Ledger/redeem có trong source | Chưa test cấp/đổi/hoàn điểm. |
| 23 | Quy trình thuê | Đạt API một phần | API-21 lịch trùng bị từ chối, lịch không trùng được tạo | Chưa test hủy, nhận/trả, ký quỹ, bồi thường hoặc gia hạn. |
| 24 | Subscription | Chưa kiểm thử | API có trong source | Chưa test create/cancel hoặc thu định kỳ. |
| 25 | Tác động CO₂ | Chưa kiểm thử | `impact_factors`/snapshot có trong source | Chưa có test và factor khoa học có nguồn để công bố. |
| 26 | Test và báo cáo | Đạt trong phạm vi hiện có | 29/29 test (7 helper/unit, 22 API); `docs/TEST_REPORT.md` | Coverage, E2E, pentest và sandbox ngoài chưa chạy. |
| 27 | Cài/chạy Windows | Một phần | Scripts/README có trong source | Chưa thực hiện smoke test trình duyệt trong lượt này. |
| 28 | Không có secret thật trong source | Rà soát một phần | `.env.example`, `.gitignore`, cấu hình payment | Cần kiểm tra gói bàn giao và DB/QR trước khi chia sẻ công khai. |
| 29 | Nghiệp vụ cốt lõi có backend | Một phần | Có bằng chứng cho một số API trong `docs/TEST_REPORT.md` | Review, refund/return, recurring charge và E2E còn thiếu kiểm chứng. |

## Quyết định nghiệm thu

**Chưa đủ căn cứ nghiệm thu toàn bộ.** Các luồng chưa có test, giao dịch ngoài, browser/E2E, coverage, vận hành production và yếu tố môi trường cần được kiểm tra riêng trước khi đưa ra kết luận rộng hơn.
