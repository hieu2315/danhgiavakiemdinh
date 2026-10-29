"""Create clearly labeled, fictional demo accounts and transactions in a local database."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import app


ACCOUNTS = [
    ("Khách Demo", "customer@reloop.local", "CustomerDemo!2026", "customer"),
    ("Người bán cá nhân Demo", "seller.personal@reloop.local", "SellerDemo!2026", "seller"),
    ("Cửa hàng Demo", "seller.business@reloop.local", "BusinessDemo!2026", "seller"),
]


def main():
    if os.environ.get("RELOOP_ENV", "development").lower() == "production":
        raise SystemExit("Refusing to seed demo users or fictional transactions in production.")
    app.init_db()
    now = int(time.time())
    ids = {}
    with app.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        admin_email = os.environ.get("RELOOP_ADMIN_EMAIL", "admin@reloop.local").strip()
        admin_password = os.environ.get("RELOOP_ADMIN_PASSWORD", "")
        if admin_email and admin_password:
            admin_row = db.execute("SELECT id,role,password_hash FROM users WHERE email=?", (admin_email,)).fetchone()
            if not admin_row:
                cur = db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", ("Quản trị viên Demo", admin_email, app.password_hash(admin_password), "admin", now))
                admin_id = cur.lastrowid
            else:
                admin_id = admin_row["id"]
                if admin_row["role"] != "admin" or not app.password_matches(admin_password, admin_row["password_hash"]):
                    db.execute("UPDATE users SET name='Quản trị viên Demo',password_hash=?,role='admin' WHERE id=?", (app.password_hash(admin_password), admin_id))
                    db.execute("DELETE FROM sessions WHERE user_id=?", (admin_id,))
                    db.execute("INSERT INTO audit_log(actor_id,action,entity_type,entity_id,details,created_at) VALUES(?, 'admin.demo_provisioned','user',?,'Local-only demo admin role/password provisioned from environment; prior sessions revoked',?)", (admin_id, str(admin_id), now))
        for name, email, password, role in ACCOUNTS:
            row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if row:
                user_id = row["id"]
            else:
                cur = db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", (name, email, app.password_hash(password), role, now))
                user_id = cur.lastrowid
            ids[email] = user_id
        personal = ids["seller.personal@reloop.local"]
        business = ids["seller.business@reloop.local"]
        customer = ids["customer@reloop.local"]
        for uid, kind, display, description in (
            (personal, "c2c", "Linh Demo · Hà Nội", "Hồ sơ người bán cá nhân dùng trong dữ liệu trình diễn."),
            (business, "b2c", "Xưởng Xanh Demo · Đà Nẵng", "Hồ sơ cửa hàng hư cấu dùng trong dữ liệu trình diễn."),
        ):
            db.execute("INSERT OR IGNORE INTO seller_profiles(user_id,business_type,display_name,description,status,created_at) VALUES(?,?,?,?, 'approved',?)", (uid, kind, display, description, now))
            db.execute("UPDATE users SET role='seller' WHERE id=? AND role!='admin'", (uid,))
        for pid in ("p13", "p14", "p15", "p16"):
            db.execute("UPDATE products SET owner_id=?,seller_type='c2c',seller='Linh Demo · Hà Nội' WHERE id=? AND owner_id IS NULL", (personal, pid))
        for pid in ("p17", "p18", "p19", "p20"):
            db.execute("UPDATE products SET owner_id=?,seller_type='b2c',seller='Xưởng Xanh Demo · Đà Nẵng' WHERE id=? AND owner_id IS NULL", (business, pid))

        sample_orders = [
            ("DEMO-ORD-001",  "p13", 1, "Đang xử lý", "COD", "unpaid", 3),
            ("DEMO-ORD-002",  "p15", 1, "Đang giao", "COD", "unpaid", 5),
            ("DEMO-ORD-003",  "p13", 1, "Hoàn tất", "COD", "paid", 12),
            ("DEMO-ORD-004",  "p17", 1, "Đã hủy", "VNPAY", "cancelled", 16),
        ]
        for order_id, product_id, quantity, status, payment, payment_status, age_days in sample_orders:
            if db.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone():
                continue
            product = db.execute("SELECT name,price FROM products WHERE id=?", (product_id,)).fetchone()
            created = now - age_days * 86400
            total = product["price"] * quantity
            db.execute("INSERT INTO orders(id,user_id,total,payment,status,kind,address,created_at,points_awarded,provider_reference,payment_status,accepted_terms_version,terms_accepted_at,is_demo) VALUES(?,?,?,?,?,'purchase','DEMO DATA — không giao hàng thật',?, ?,NULL,?,'demo-seed-v1',?,1)", (order_id, customer, total, payment, status, created, 1 if status == "Hoàn tất" else 0, payment_status, created))
            cur = db.execute("INSERT INTO order_items(order_id,product_id,name,price,quantity,fulfillment_status) VALUES(?,?,?,?,?,?)", (order_id, product_id, product["name"], product["price"], quantity, status))
            item_id = cur.lastrowid
            db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)", (order_id, "Đang xử lý", customer, "DEMO — đơn giao dịch giả lập", created))
            if status != "Đang xử lý":
                db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)", (order_id, status, customer, "DEMO — trạng thái mẫu, không phải giao dịch thật", created + 3600))
            db.execute("INSERT INTO payment_status_history(order_id,payment_status,actor_id,source,note,created_at) VALUES(?,?,?,?,?,?)", (order_id, payment_status, customer, "demo_seed", "DEMO — trạng thái thanh toán giả lập; không có tiền được thu", created + 3600))
            if payment == "VNPAY":
                db.execute("INSERT INTO payment_transactions(order_id,provider,txn_ref,amount,status,created_at,updated_at) VALUES(?,'VNPAY',?,?, 'cancelled',?,?)", (order_id, "DEMO-TXN-004", total, created, created + 3600))
            if order_id == "DEMO-ORD-003":
                db.execute("INSERT OR IGNORE INTO points_ledger(user_id,points,event_type,reference_type,reference_id,note,created_at) VALUES(?,85,'earn','order',?,'DEMO — điểm minh họa, không có giá trị tiền thật',?)", (customer, order_id, created + 3600))
                for rating, body in ((5, "Đánh giá minh họa cho giao diện đồ án."), (4, "Nội dung giả lập, không phải phản hồi của khách hàng thật.")):
                    pid = "p13" if rating == 5 else "p14"
                    if pid == "p14":
                        db.execute("INSERT OR IGNORE INTO order_items(order_id,product_id,name,price,quantity) SELECT ?,id,name,price,1 FROM products WHERE id='p14'", (order_id,))
                        db.execute("UPDATE orders SET total=(SELECT SUM(price*quantity) FROM order_items WHERE order_id=?) WHERE id=?", (order_id,order_id))
                    db.execute("INSERT OR IGNORE INTO reviews(order_id,product_id,user_id,rating,body,status,created_at,is_demo) VALUES(?,?,?,?,?,'approved',?,1)", (order_id, pid, customer, rating, body, created + 7200))

        plans = (("ReBox Basic", 99000, "active", "monthly", 30), ("ReBox Plus", 199000, "cancelled", "monthly", 60))
        for plan, price, status, cadence, age in plans:
            if not db.execute("SELECT 1 FROM subscriptions WHERE user_id=? AND plan=?", (customer, plan)).fetchone():
                started = now - age * 86400
                db.execute("INSERT INTO subscriptions(user_id,plan,price,status,created_at,cadence,starts_at,next_due_at,cancelled_at) VALUES(?,?,?,?,?,?,?,?,?)", (customer, plan, price, status, started, cadence, time.strftime('%Y-%m-%d', time.gmtime(started)), time.strftime('%Y-%m-%d', time.gmtime(started + 30 * 86400)), started + 15 * 86400 if status == "cancelled" else None))

    admin = os.environ.get("RELOOP_ADMIN_EMAIL", "admin@reloop.local")
    print("Local demo database ready. Orders, reviews, and reward points are fictional DEMO records.")
    print("Customer demo: customer@reloop.local / CustomerDemo!2026")
    print("Personal seller demo: seller.personal@reloop.local / SellerDemo!2026")
    print("Business seller demo: seller.business@reloop.local / BusinessDemo!2026")
    print(f"Admin demo: {admin} / password is configured by RELOOP_ADMIN_PASSWORD.")
    print("Do not use demo credentials on a public server or in production.")


if __name__ == "__main__":
    main()
