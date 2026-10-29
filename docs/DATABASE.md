# Cơ sở dữ liệu

Schema hiện hành dùng **SQLite**, không MySQL. Dùng `docs/DATABASE_SCHEMA.md` làm tài liệu schema chi tiết: bảng/quan hệ, migration, index, tiền VND integer, Unix epoch UTC, giao dịch, append-only và các giới hạn cart/shipment/RBAC.

- DB path: `RELOOP_DB` (mặc định `./reloop.sqlite3`).
- Migration chạy tự động, tuần tự, khi `python server.py` hoặc `init_db()` khởi động; migrations ở `database/migrations/`.
- Seed catalog chạy một lần qua `applied_seeds`; các seed SQL ở `database/seeds/`. Script `scripts/seed_demo.py` tạo tài khoản và giao dịch hư cấu riêng cho local, không chạy production.
- Backup/restore: `scripts/db_maintenance.py`; hướng dẫn thao tác trong README. Backup thủ công, chưa có scheduler.
- Database demo hiện có 14 migrations và 2 seeds. Migration 014 thêm khối lượng sản phẩm (gram) và các trường phí giao hàng/trọng lượng đã chốt theo đơn. Không xóa thủ công migration/seed đã áp dụng trên database có dữ liệu.

Sau khi restore, chạy ứng dụng trên bản sao staging và kiểm tra login, catalog, `PRAGMA integrity_check` và `PRAGMA foreign_key_check` trước khi chuyển traffic.
