"""ReLoop Market local application server (Python stdlib + SQLite)."""
from __future__ import annotations

import hashlib
import hmac
import json
import base64
import binascii
import bcrypt
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from datetime import date, timedelta
from contextlib import contextmanager
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from backend import emailer, email_templates

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
MIGRATIONS_DIR = ROOT / "database" / "migrations"
SEEDS_DIR = ROOT / "database" / "seeds"
DB_PATH = Path(os.environ.get("RELOOP_DB", ROOT / "reloop.sqlite3"))
HOST = os.environ.get("RELOOP_HOST", "127.0.0.1")
PORT = int(os.environ.get("RELOOP_PORT", "8000"))
COOKIE = "reloop_session"
SESSION_SECONDS = 60 * 60 * 24 * 7
COOKIE_SECURE = os.environ.get("RELOOP_COOKIE_SECURE", "0") == "1"
COOKIE_SECURE_ATTRIBUTE = "; Secure" if COOKIE_SECURE else ""
POLICY_VERSION = os.environ.get("RELOOP_POLICY_VERSION", "draft-2026-10-20")
SHIPPING_FREE_THRESHOLD_GRAMS = 3000
SHIPPING_UNDER_THRESHOLD_FEE = 30000
PUBLIC_SITE_FIELDS = {"operator_name":"RELOOP_OPERATOR_NAME","operator_type":"RELOOP_OPERATOR_TYPE","representative":"RELOOP_OPERATOR_REPRESENTATIVE","tax_code":"RELOOP_OPERATOR_TAX_CODE","address":"RELOOP_OPERATOR_ADDRESS","email":"RELOOP_CONTACT_EMAIL","phone":"RELOOP_CONTACT_PHONE","complaint_channel":"RELOOP_COMPLAINT_CHANNEL","privacy_contact":"RELOOP_PRIVACY_CONTACT","retention_policy":"RELOOP_DATA_RETENTION_POLICY"}
DB_LOCK = threading.RLock()
UPLOAD_DIR = ROOT / "storage" / "uploads"
LEGACY_UPLOAD_DIR = FRONTEND_DIR / "assets" / "uploads"

def vnpay_settings():
    return {
        "tmn_code": os.environ.get("RELOOP_VNPAY_TMN_CODE", "").strip(),
        "hash_secret": os.environ.get("RELOOP_VNPAY_HASH_SECRET", "").strip(),
        "return_url": os.environ.get("RELOOP_VNPAY_RETURN_URL", "").strip(),
        "ipn_url": os.environ.get("RELOOP_VNPAY_IPN_URL", "").strip(),
        "pay_url": os.environ.get("RELOOP_VNPAY_PAY_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html").strip(),
    }

def vnpay_signature(params, secret):
    canonical = urlencode(sorted((k, str(v)) for k, v in params.items() if k not in ("vnp_SecureHash", "vnp_SecureHashType")))
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha512).hexdigest()

def build_vnpay_url(order_id, amount, client_ip, now=None):
    cfg=vnpay_settings()
    if not all(cfg[k] for k in ("tmn_code","hash_secret","return_url","ipn_url")):
        raise APIError(503,"VNPay sandbox chưa được cấu hình đầy đủ; chưa tạo đơn hàng")
    parsed=urlparse(cfg['pay_url'])
    if parsed.scheme!='https' or parsed.hostname not in ('sandbox.vnpayment.vn',):
        raise APIError(503,"Địa chỉ VNPay phải là endpoint sandbox HTTPS chính thức")
    now=now or time.localtime()
    expire_minutes=max(5,min(30,int(os.environ.get('RELOOP_VNPAY_EXPIRE_MINUTES','15'))))
    import datetime
    from zoneinfo import ZoneInfo
    vn_now=datetime.datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) if now is None else datetime.datetime.fromtimestamp(time.mktime(now),ZoneInfo('Asia/Ho_Chi_Minh'))
    created=vn_now.strftime('%Y%m%d%H%M%S')
    expires=(vn_now+datetime.timedelta(minutes=expire_minutes)).strftime('%Y%m%d%H%M%S')
    params={"vnp_Version":"2.1.0","vnp_Command":"pay","vnp_TmnCode":cfg['tmn_code'],"vnp_Amount":str(amount*100),"vnp_CurrCode":"VND","vnp_TxnRef":order_id,"vnp_OrderInfo":f"Thanh toan don hang {order_id}","vnp_OrderType":"other","vnp_Locale":"vn","vnp_ReturnUrl":cfg['return_url'],"vnp_CreateDate":created,"vnp_ExpireDate":expires,"vnp_IpAddr":client_ip[:45]}
    params['vnp_SecureHash']=vnpay_signature(params,cfg['hash_secret'])
    return cfg['pay_url']+'?'+urlencode(sorted(params.items())), int(time.time())+expire_minutes*60

def expire_vnpay_orders(db, now=None):
    now=now or int(time.time())
    rows=db.execute("SELECT id,user_id FROM orders WHERE payment='VNPAY' AND payment_status IN ('pending','failed') AND payment_expires_at IS NOT NULL AND payment_expires_at<=? AND status NOT IN ('Đã hủy','Hoàn tất')",(now,)).fetchall()
    for row in rows:
        for item in db.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?",(row['id'],)).fetchall():
            db.execute("UPDATE products SET stock=stock+?,lifecycle_status=CASE WHEN lifecycle_status='out_of_stock' AND status='approved' THEN 'active' ELSE lifecycle_status END,updated_at=? WHERE id=?",(item['quantity'],now,item['product_id']))
        db.execute("UPDATE orders SET status='Đã hủy',payment_status='expired' WHERE id=?",(row['id'],))
        db.execute("UPDATE payment_transactions SET status='expired',updated_at=? WHERE order_id=? AND status='pending'",(now,row['id']))
        db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,'Đã hủy',?,'Thanh toán VNPay quá thời hạn; tồn kho được giải phóng',?)",(row['id'],row['user_id'],now))
        db.execute("INSERT INTO payment_status_history(order_id,payment_status,source,note,created_at) VALUES(?,'expired','expiry_job','Hết thời hạn thanh toán VNPay',?)",(row['id'],now))
        db.execute("INSERT INTO audit_log(actor_id,action,entity_type,entity_id,details,created_at) VALUES(NULL,'payment.expired','order',?,'VNPay hết hạn; tồn kho được hoàn lại',?)",(row['id'],now))

def slugify(value: str) -> str:
    value=unicodedata.normalize('NFKD',value)
    value=''.join(c for c in value if not unicodedata.combining(c)).lower()
    value=value.replace('đ','d')
    value=re.sub(r'[^a-z0-9]+','-',value).strip('-')
    return value[:120] or 'san-pham'

def safe_product_text(value, limit, field):
    if not isinstance(value,str): raise APIError(400,f"{field} không hợp lệ")
    value=value.strip()
    if len(value)>limit or re.search(r'<\s*/?\s*[a-z!]|javascript\s*:|data\s*:\s*text/html',value,re.I): raise APIError(400,f"{field} quá dài hoặc chứa HTML không được hỗ trợ")
    return value

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def password_hash(password: str, salt: bytes | None = None) -> str:
    encoded=password.encode('utf-8')
    if len(encoded)>72: raise ValueError("Mật khẩu tối đa 72 byte UTF-8 khi dùng bcrypt")
    return bcrypt.hashpw(encoded,bcrypt.gensalt(rounds=12)).decode('ascii')

def password_matches(password: str, stored: str) -> bool:
    encoded=password.encode('utf-8')
    if stored.startswith(('$2a$','$2b$','$2y$')):
        if len(encoded)>72: return False
        try: return bcrypt.checkpw(encoded,stored.encode('ascii'))
        except (ValueError,TypeError): return False
    try:
        salt_hex,_=stored.split(':',1); salt=bytes.fromhex(salt_hex)
        derived=hashlib.pbkdf2_hmac('sha256',encoded,salt,310_000)
        return hmac.compare_digest(salt_hex+':'+derived.hex(),stored)
    except (ValueError,TypeError): return False

def password_needs_rehash(stored):
    return not stored.startswith('$2b$12$')

DUMMY_PASSWORD_HASH=bcrypt.hashpw(secrets.token_bytes(32),bcrypt.gensalt(rounds=12))

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK, connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if not db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (migration.name,)).fetchone():
                db.executescript(migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(?,?)", (migration.name,int(time.time())))
        db.execute("CREATE TABLE IF NOT EXISTS applied_seeds(name TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)")
        for seed in sorted(SEEDS_DIR.glob("*.sql")):
            if not db.execute("SELECT 1 FROM applied_seeds WHERE name=?", (seed.name,)).fetchone():
                db.executescript(seed.read_text(encoding="utf-8"))
                db.execute("INSERT INTO applied_seeds(name,applied_at) VALUES(?,?)", (seed.name,int(time.time())))
        for product in db.execute("SELECT id,name FROM products WHERE slug='' OR slug IS NULL").fetchall():
            base_slug=slugify(product['name']); candidate=base_slug
            if db.execute("SELECT 1 FROM products WHERE slug=?",(candidate,)).fetchone(): candidate=(base_slug[:105]+'-'+slugify(product['id']))[:120]
            db.execute("UPDATE products SET slug=? WHERE id=?",(candidate,product['id']))
        db.execute("UPDATE products SET category_id=(SELECT id FROM categories WHERE slug=CASE category WHEN 'Điện tử' THEN 'dien-tu' WHEN 'Thời trang' THEN 'thoi-trang' WHEN 'Đồ gia dụng' THEN 'do-gia-dung' WHEN 'Nội thất' THEN 'do-gia-dung' ELSE 'san-pham-tai-che' END),item_type=CASE WHEN category='Tái chế' THEN 'recycled' ELSE 'used' END,rental_price_day=CASE WHEN rentable=1 AND rental_price_day=0 THEN 49000 ELSE rental_price_day END WHERE category_id IS NULL")
        admin_email = os.environ.get("RELOOP_ADMIN_EMAIL")
        admin_password = os.environ.get("RELOOP_ADMIN_PASSWORD")
        if admin_email and admin_password:
            db.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", ("Quản trị viên", admin_email, password_hash(admin_password), "admin", int(time.time())))

class APIError(Exception):
    def __init__(self, status: int, message: str): self.status, self.message = status, message

def recommend_products(db, user, context, product_id=None, cart_ids=None, limit=8):
    limit=max(1,min(12,int(limit)))
    source_ids=[]
    sources=[]
    if product_id:
        source=db.execute("SELECT id,category,item_type,condition,price,rentable FROM products WHERE id=? AND status='approved' AND lifecycle_status='active'",(product_id,)).fetchone()
        if not source: raise APIError(404,"Không tìm thấy sản phẩm")
        source_ids.append(source['id'])
        sources.append(source)
    if context=='cart' and cart_ids:
        requested=list(dict.fromkeys(str(product_id).strip() for product_id in cart_ids if str(product_id).strip()))[:20]
        if requested:
            placeholders=','.join('?' for _ in requested)
            rows=db.execute(f"SELECT id,category,item_type,condition,price,rentable FROM products WHERE id IN ({placeholders}) AND status='approved' AND lifecycle_status='active'",requested).fetchall()
            for source in rows:
                if source['id'] not in source_ids:
                    source_ids.append(source['id'])
                    sources.append(source)

    favorite_categories=set()
    ordered_categories=set()
    if user:
        for row in db.execute("SELECT DISTINCT p.category FROM favorites f JOIN products p ON p.id=f.product_id WHERE f.user_id=?",(user['id'],)).fetchall():
            favorite_categories.add(row['category'])
        for row in db.execute("SELECT DISTINCT p.category FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id WHERE o.user_id=? AND o.is_demo=0 AND o.status!='Đã hủy'",(user['id'],)).fetchall():
            ordered_categories.add(row['category'])

    exclusions=list(source_ids)
    params=[]
    filters=["p.status='approved'","p.lifecycle_status='active'","(p.stock>0 OR p.rentable=1)"]
    if user:
        filters.append("(p.owner_id IS NULL OR p.owner_id!=?)")
        params.append(user['id'])
    if exclusions:
        filters.append("p.id NOT IN ("+','.join('?' for _ in exclusions)+")")
        params.extend(exclusions)
    candidates=db.execute(
        "SELECT p.id,p.name,p.slug,p.category,p.condition,p.seller,p.price,p.emoji,p.bg,p.badge,p.rentable AS rent,p.item_type,p.stock,p.created_at,"
        "(SELECT i.image_path FROM product_images i WHERE i.product_id=p.id ORDER BY i.sort_order,i.id LIMIT 1) image,"
        "COALESCE((SELECT SUM(oi.quantity) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id AND o.status='Hoàn tất' AND o.is_demo=0),0) sold_quantity,"
        "COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.product_id=p.id AND r.status='approved' AND r.is_demo=0),0) rating_average,"
        "COALESCE((SELECT COUNT(*) FROM reviews r WHERE r.product_id=p.id AND r.status='approved' AND r.is_demo=0),0) rating_count "
        "FROM products p WHERE "+" AND ".join(filters),params).fetchall()

    together={}
    if source_ids:
        placeholders=','.join('?' for _ in source_ids)
        rows=db.execute(
            "SELECT candidate.product_id,COUNT(DISTINCT candidate.order_id) order_count "
            "FROM order_items candidate JOIN order_items source_item ON source_item.order_id=candidate.order_id "
            "JOIN orders o ON o.id=candidate.order_id "
            f"WHERE source_item.product_id IN ({placeholders}) AND candidate.product_id NOT IN ({placeholders}) "
            "AND o.is_demo=0 AND o.status!='Đã hủy' GROUP BY candidate.product_id",
            (*source_ids,*source_ids)).fetchall()
        together={row['product_id']:row['order_count'] for row in rows}

    ranked=[]
    for row in candidates:
        product=dict(row)
        co_purchases=together.get(product['id'],0)
        same_category=max((source['category']==product['category'] for source in sources),default=False)
        similar_score=max((int(source['category']==product['category'])*4
                           +int(source['item_type']==product['item_type'])*2
                           +int(source['condition']==product['condition'])
                           +int(abs(source['price']-product['price'])<=max(10000,source['price']*.25))
                           +int(source['rentable']==product['rent']) for source in sources),default=0)
        favorite_match=bool(user and product['category'] in favorite_categories)
        order_match=bool(user and product['category'] in ordered_categories)
        popular_score=min(product['sold_quantity'],100)*0.5+product['rating_average']*2+min(product['rating_count'],20)*0.1
        score=similar_score+co_purchases*5+popular_score
        if favorite_match: score+=8
        elif order_match: score+=4
        reason=("Thường được mua cùng" if co_purchases else
                "Dựa trên mục yêu thích của bạn" if favorite_match else
                "Cùng danh mục" if same_category else
                "Bán chạy" if product['sold_quantity'] else "Mới đăng")
        product['reason']=reason
        product['_score']=score
        product['_co_purchases']=co_purchases
        ranked.append(product)
    ranked.sort(key=lambda item:(-item['_score'],-item['_co_purchases'],-item['sold_quantity'],-item['rating_average'],-item['created_at'],item['id']))
    items=[]
    for product in ranked[:limit]:
        product.pop('_score')
        product.pop('_co_purchases')
        product.pop('created_at')
        items.append(product)
    return {"method":"hybrid-rule-based" if user else "rule-based","items":items}

class Handler(SimpleHTTPRequestHandler):
    server_version = "ReLoop/1.0"
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)
    sys_version = ""
    def log_message(self, fmt, *args):
        message=fmt % args
        if 'vnpay/ipn' in message or 'vnpay/return' in message:
            message=re.sub(r'"(GET )[^ ?]+\?[^ ]+( HTTP/[0-9.]+)"',r'"\1[callback query redacted]\2"',message)
        print("%s - %s" % (self.log_date_time_string(),message))

    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy","default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'")
        if COOKIE_SECURE: self.send_header("Strict-Transport-Security","max-age=31536000; includeSubDomains")
        super().end_headers()

    def audit_security(self,db,event_type,ip_hash='',account_hash='',user_id=None):
        db.execute("INSERT INTO security_events(event_type,ip_hash,account_hash,user_id,created_at) VALUES(?,?,?,?,?)",(event_type,ip_hash,account_hash,user_id,int(time.time())))

    def login_bucket_state(self,db,bucket_key,limit,now):
        row=db.execute("SELECT failures,window_started,blocked_until FROM login_attempt_buckets WHERE bucket_key=?",(bucket_key,)).fetchone()
        if row and row['blocked_until']>now: return row['blocked_until']
        if not row or now-row['window_started']>=900:
            db.execute("INSERT INTO login_attempt_buckets(bucket_key,failures,window_started,blocked_until) VALUES(?,0,?,0) ON CONFLICT(bucket_key) DO UPDATE SET failures=0,window_started=excluded.window_started,blocked_until=0",(bucket_key,now))
            return 0
        return 0

    def record_login_failure(self,db,ip_hash,account_hash,now):
        for bucket_key,limit in (("ip:"+ip_hash,20),("account:"+account_hash,8)):
            self.login_bucket_state(db,bucket_key,limit,now)
            row=db.execute("SELECT failures,window_started FROM login_attempt_buckets WHERE bucket_key=?",(bucket_key,)).fetchone()
            failures=row['failures']+1
            blocked=now+min(300,30*2**min(max(0,failures-limit),4)) if failures>=limit else 0
            db.execute("UPDATE login_attempt_buckets SET failures=?,blocked_until=? WHERE bucket_key=?",(failures,blocked,bucket_key))
        self.audit_security(db,'login.failure',ip_hash,account_hash)

    def send_json(self, status, payload, headers=None):
        body=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

    def send_bytes(self,status,body,content_type):
        self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(body))); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)

    def serve_404(self):
        body=(FRONTEND_DIR/'404.html').read_bytes()
        self.send_bytes(404,body,'text/html; charset=utf-8')

    def send_response_redirect(self, location):
        self.send_response(303); self.send_header('Location',location); self.send_header('Cache-Control','no-store'); self.end_headers()

    def read_json(self,max_bytes=32_000):
        try:
            raw_length=self.headers.get("Content-Length")
            if raw_length is None: raise APIError(411,"Yêu cầu cần có Content-Length")
            length=int(raw_length)
            if length<1: raise APIError(400,"Dữ liệu gửi lên trống")
            if length > max_bytes: raise APIError(413,"Dữ liệu gửi lên quá lớn")
            if not self.headers.get("Content-Type","").startswith("application/json"): raise APIError(415,"Yêu cầu Content-Type application/json")
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise APIError(400,"Dữ liệu không hợp lệ")
            return data
        except (ValueError, json.JSONDecodeError): raise APIError(400,"JSON không hợp lệ")

    def current_user(self, required=False, admin=False):
        raw=self.cookies().get(COOKIE)
        user=None
        if raw:
            with connect() as db:
                user=db.execute("SELECT u.id,u.name,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",(hashlib.sha256(raw.encode()).hexdigest(),int(time.time()))).fetchone()
        if required and not user: raise APIError(401,"Vui lòng đăng nhập")
        if admin and user and user["role"]!="admin": raise APIError(403,"Bạn không có quyền quản trị")
        if admin and not user: raise APIError(401,"Vui lòng đăng nhập bằng tài khoản quản trị")
        return dict(user) if user else None

    def require_role(self, *roles):
        user=self.current_user(True)
        if user['role'] not in roles: raise APIError(403,"Vai trò tài khoản không được phép thực hiện thao tác này")
        return user

    @staticmethod
    def audit(db, actor, action, entity_type, entity_id, details=''):
        db.execute("INSERT INTO audit_log(actor_id,action,entity_type,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",(actor['id'],action,entity_type,str(entity_id),details[:500],int(time.time())))

    @staticmethod
    def audit_event(db, actor_id, action, entity_type, entity_id, details=''):
        db.execute("INSERT INTO audit_log(actor_id,action,entity_type,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",(actor_id,action,entity_type,str(entity_id),details[:500],int(time.time())))

    def queue_email(self, user_id, subject, body):
        with connect() as db:
            row=db.execute("SELECT email FROM users WHERE id=?",(user_id,)).fetchone()
            if not row: return None
            cur=db.execute("INSERT INTO notification_outbox(user_id,kind,subject,body,status,created_at) VALUES(?,?,?,?,?,?)",(user_id,'email',subject,body,'pending',int(time.time())))
            notice_id=cur.lastrowid; recipient=row['email']
        if emailer.configured():
            try:
                emailer.send(recipient,subject,body)
                with connect() as db: db.execute("UPDATE notification_outbox SET status='sent',sent_at=?,error='' WHERE id=?",(int(time.time()),notice_id))
            except Exception as exc:
                with connect() as db: db.execute("UPDATE notification_outbox SET status='failed',error=? WHERE id=?",(str(exc)[:300],notice_id))
        with connect() as db: return db.execute("SELECT status FROM notification_outbox WHERE id=?",(notice_id,)).fetchone()['status']

    @staticmethod
    def voucher_discount(db,user,code,subtotal):
        if not code: return None,0
        voucher=db.execute("SELECT * FROM vouchers WHERE code=? COLLATE NOCASE AND is_active=1",(code.strip(),)).fetchone()
        now=int(time.time())
        if not voucher or not voucher['starts_at']<=now<=voucher['ends_at']: raise APIError(400,"Mã giảm giá không tồn tại, chưa bắt đầu hoặc đã hết hạn")
        if subtotal<voucher['min_order']: raise APIError(400,"Giá trị đơn chưa đạt mức tối thiểu của mã giảm giá")
        used=db.execute("SELECT COUNT(*) FROM voucher_redemptions WHERE voucher_id=?",(voucher['id'],)).fetchone()[0]
        personal=db.execute("SELECT COUNT(*) FROM voucher_redemptions WHERE voucher_id=? AND user_id=?",(voucher['id'],user['id'])).fetchone()[0]
        if voucher['usage_limit'] is not None and used>=voucher['usage_limit']: raise APIError(409,"Mã giảm giá đã hết lượt sử dụng")
        if personal>=voucher['per_user_limit']: raise APIError(409,"Bạn đã sử dụng hết lượt cho mã giảm giá này")
        discount=(subtotal*voucher['value']//100) if voucher['discount_type']=='percent' else voucher['value']
        if voucher['max_discount'] is not None: discount=min(discount,voucher['max_discount'])
        return voucher,min(subtotal,discount)

    def cookies(self):
        from http.cookies import SimpleCookie
        c=SimpleCookie(); c.load(self.headers.get("Cookie","")); return {k:v.value for k,v in c.items()}

    def check_origin(self,require_origin=False):
        origin=self.headers.get("Origin")
        if not origin and self.headers.get("Referer"): origin=self.headers.get("Referer")
        if not origin:
            if require_origin: raise APIError(403,"Thiếu Origin/Referer cho yêu cầu thay đổi dữ liệu")
            return
        parsed=urlparse(origin)
        if parsed.netloc != self.headers.get("Host") or parsed.scheme not in ("http","https"):
            raise APIError(403,"Origin không hợp lệ")

    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/payments/vnpay/return":
                params={k:v[-1] for k,v in parse_qs(urlparse(self.path).query).items()}
                oid=params.get('vnp_TxnRef','')
                with connect() as db:
                    row=db.execute("SELECT id FROM orders WHERE id=?",(oid,)).fetchone()
                cfg=vnpay_settings(); result='verified' if row and cfg['hash_secret'] and params.get('vnp_TmnCode')==cfg['tmn_code'] and hmac.compare_digest(params.get('vnp_SecureHash',''),vnpay_signature(params,cfg['hash_secret'])) else 'unverified'
                return self.send_response_redirect('/?payment_return=1&order='+oid+'&result='+result)
            if path=="/api/payments/vnpay/ipn":
                params={k:v[-1] for k,v in parse_qs(urlparse(self.path).query).items()}
                cfg=vnpay_settings(); code='97'
                if cfg['hash_secret'] and params.get('vnp_TmnCode')==cfg['tmn_code'] and params.get('vnp_CurrCode')=='VND' and hmac.compare_digest(params.get('vnp_SecureHash',''),vnpay_signature(params,cfg['hash_secret'])):
                    code='01'
                    with connect() as db:
                        db.execute('BEGIN IMMEDIATE')
                        expire_vnpay_orders(db)
                        tx=db.execute("SELECT t.*,o.payment_status,o.status order_status,o.total FROM payment_transactions t JOIN orders o ON o.id=t.order_id WHERE t.txn_ref=? AND t.provider='VNPAY'",(params.get('vnp_TxnRef',''),)).fetchone()
                        if tx:
                            try: amount=int(params.get('vnp_Amount','-1'))
                            except ValueError: amount=-1
                            provider_success=params.get('vnp_ResponseCode')=='00' and params.get('vnp_TransactionStatus')=='00'
                            terminal=tx['status'] in ('success','failed','cancelled','expired','late_success')
                            reopen_success=provider_success and tx['status'] in ('failed','cancelled','expired')
                            code='04' if amount!=tx['amount']*100 else ('02' if terminal and not reopen_success else '00')
                            if code=='00' and tx['status']!='success':
                                success=params.get('vnp_ResponseCode')=='00' and params.get('vnp_TransactionStatus')=='00'
                                new_status='success' if success else ('cancelled' if params.get('vnp_ResponseCode')=='24' else ('expired' if params.get('vnp_ResponseCode')=='08' else 'failed'))
                                now=int(time.time())
                                if (tx['order_status']=='Đã hủy' or tx['status'] in ('cancelled','expired')) and success: new_status='late_success'
                                db.execute("UPDATE payment_transactions SET status=?,provider_transaction_no=?,response_code=?,updated_at=? WHERE id=?",(new_status,params.get('vnp_TransactionNo'),params.get('vnp_ResponseCode'),now,tx['id']))
                                if new_status=='success':
                                    db.execute("UPDATE orders SET payment_status='paid' WHERE id=?",(tx['order_id'],))
                                    db.execute("INSERT INTO payment_status_history(order_id,payment_status,source,note,created_at) VALUES(?,'paid','vnpay_ipn','VNPay xác nhận giao dịch thành công',?)",(tx['order_id'],now))
                                elif new_status=='late_success':
                                    db.execute("INSERT INTO payment_status_history(order_id,payment_status,source,note,created_at) VALUES(?,'unpaid','vnpay_ipn','Thanh toán đến sau khi đơn đã hủy; cần đối soát thủ công',?)",(tx['order_id'],now))
                                elif new_status in ('cancelled','expired'):
                                    if tx['order_status']!='Đã hủy':
                                        for item in db.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?",(tx['order_id'],)).fetchall():
                                            db.execute("UPDATE products SET stock=stock+?,lifecycle_status=CASE WHEN lifecycle_status='out_of_stock' AND status='approved' THEN 'active' ELSE lifecycle_status END,updated_at=? WHERE id=?",(item['quantity'],now,item['product_id']))
                                        db.execute("UPDATE orders SET status='Đã hủy' WHERE id=?",(tx['order_id'],))
                                        db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,'Đã hủy',?,'Thanh toán VNPay bị hủy/hết hạn; đã giải phóng tồn kho',?)",(tx['order_id'],None,now))
                                    payment_state='cancelled' if new_status=='cancelled' else 'expired'
                                    db.execute("UPDATE orders SET payment_status=? WHERE id=?",(payment_state,tx['order_id']))
                                    db.execute("INSERT INTO payment_status_history(order_id,payment_status,source,note,created_at) VALUES(?,?,'vnpay_ipn',?,?)",(tx['order_id'],payment_state,'VNPay trả về '+str(params.get('vnp_ResponseCode','')),now))
                                else:
                                    db.execute("UPDATE orders SET payment_status='failed' WHERE id=?",(tx['order_id'],))
                                    db.execute("INSERT INTO payment_status_history(order_id,payment_status,source,note,created_at) VALUES(?,'failed','vnpay_ipn',?,?)",(tx['order_id'],'VNPay trả về '+str(params.get('vnp_ResponseCode','')),now))
                                db.execute("INSERT INTO audit_log(actor_id,action,entity_type,entity_id,details,created_at) VALUES(NULL,'payment.vnpay_callback','order',?,?,?)",(tx['order_id'],'status='+new_status,now))
                return self.send_json(200,{"RspCode":code,"Message":{"00":"Confirm Success","01":"Order not Found","02":"Order already confirmed","04":"Invalid Amount","97":"Invalid Signature"}.get(code,"Failed")})
            if not path.startswith("/api/"):
                if path == "/assets/vnpay-personal-qr.jpg":
                    qr_file=FRONTEND_DIR/"assets"/"vnpay-personal-qr.jpg"
                    if not qr_file.is_file(): return self.send_bytes(404,b"QR image is missing from frontend/assets.","text/plain; charset=utf-8")
                    body=qr_file.read_bytes(); self.send_response(200); self.send_header("Content-Type","image/jpeg"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store, max-age=0"); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(body); return
                upload_match=re.fullmatch(r"/assets/uploads/([a-f0-9]{32})\.(png|jpg|webp)",path)
                if upload_match:
                    filename=upload_match.group(1)+'.'+upload_match.group(2)
                    stored=UPLOAD_DIR/filename; legacy=LEGACY_UPLOAD_DIR/filename
                    candidate=stored if stored.is_file() else legacy
                    if not candidate.is_file(): return self.send_error(HTTPStatus.NOT_FOUND)
                    content=candidate.read_bytes(); mime={'png':'image/png','jpg':'image/jpeg','webp':'image/webp'}[upload_match.group(2)]
                    self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(content))); self.send_header('Cache-Control','public, max-age=86400'); self.send_header('Cross-Origin-Resource-Policy','same-site'); self.end_headers(); self.wfile.write(content); return
                if path=="/robots.txt":
                    body="User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /account\nDisallow: /cart\n"
                    base=os.environ.get('RELOOP_PUBLIC_BASE_URL','').strip().rstrip('/')
                    if re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?",base): body+="Sitemap: "+base+"/sitemap.xml\n"
                    return self.send_bytes(200,body.encode(),"text/plain; charset=utf-8")
                if path=="/sitemap.xml":
                    base=os.environ.get('RELOOP_PUBLIC_BASE_URL','').strip().rstrip('/')
                    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?",base):
                        return self.send_bytes(503,b"Public HTTPS base URL must be configured in RELOOP_PUBLIC_BASE_URL before sitemap generation.","text/plain; charset=utf-8")
                    from xml.sax.saxutils import escape as xml_escape
                    urls=[base+'/',base+'/guides.html',base+'/policies.html']
                    with connect() as db:
                        urls.extend(base+'/p/'+r['slug'] for r in db.execute("SELECT slug FROM products WHERE status='approved' AND lifecycle_status='active' AND stock>0 AND slug IS NOT NULL ORDER BY updated_at DESC"))
                    body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+xml_escape(u)+'</loc></url>' for u in urls)+'</urlset>'
                    return self.send_bytes(200,body.encode(),"application/xml; charset=utf-8")
                product_route=re.fullmatch(r"/p/([a-z0-9-]{1,120})",path)
                if product_route:
                    slug=product_route.group(1)
                    with connect() as db:
                        row=db.execute("SELECT id,name,slug,short_description,description,condition,category,seller,seller_type,price,stock,item_type,rentable,rental_price_day,shipping_policy,return_policy,image_path,rating_average,rating_count FROM (SELECT p.id,p.name,p.slug,p.short_description,p.description,p.condition,p.category,p.seller,p.seller_type,p.price,p.stock,p.item_type,p.rentable,p.rental_price_day,p.shipping_policy,p.return_policy,(SELECT image_path FROM product_images i WHERE i.product_id=p.id ORDER BY i.sort_order,i.id LIMIT 1) image_path,(SELECT ROUND(AVG(r.rating),1) FROM reviews r WHERE r.product_id=p.id AND r.status='approved' AND r.is_demo=0) rating_average,(SELECT COUNT(*) FROM reviews r WHERE r.product_id=p.id AND r.status='approved' AND r.is_demo=0) rating_count FROM products p WHERE p.status='approved' AND p.lifecycle_status='active') WHERE slug=? AND stock>0",(slug,)).fetchone()
                    if not row: return self.serve_404()
                    base=os.environ.get('RELOOP_PUBLIC_BASE_URL','').strip().rstrip('/')
                    canonical=(base+'/p/'+row['slug']) if re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?",base) else ''
                    esc=lambda v: str(v or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;')
                    raw_desc=(row['short_description'] or row['description'] or '').strip()
                    desc_parts=[]
                    for part in re.split(r'(?<=[.!?])\s+|\s*\n+\s*',raw_desc):
                        part=part.strip(' \t-•')
                        if part and part.casefold() not in {x.casefold() for x in desc_parts}: desc_parts.append(part)
                    desc=' '.join(desc_parts) or f"Sản phẩm {row['category'].lower()} được đăng bán trên ReLoop Market. Vui lòng xem tình trạng và thông tin người bán trước khi đặt mua."
                    image=(base+row['image_path']) if base and row['image_path'] and row['image_path'].startswith('/') else ((base+'/'+row['image_path']) if base and row['image_path'] else '')
                    ld={"@context":"https://schema.org","@type":"Product","name":row['name'],"description":desc,"sku":row['id'],"category":row['category'],"image":[image] if image else [],"offers":{"@type":"Offer","url":canonical or '/p/'+row['slug'],"priceCurrency":"VND","price":row['price'],"availability":"https://schema.org/ InStock".replace(' ','') if row['stock']>0 else "https://schema.org/OutOfStock","itemCondition":"https://schema.org/UsedCondition" if row['item_type']=='used' else "https://schema.org/NewCondition"}}
                    if row['rating_count']:
                        ld['aggregateRating']={"@type":"AggregateRating","ratingValue":row['rating_average'],"reviewCount":row['rating_count']}
                    breadcrumbs={"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Trang chủ","item":base+'/' if base else '/'},{"@type":"ListItem","position":2,"name":row['category'],"item":base+'/#products' if base else '/#products'},{"@type":"ListItem","position":3,"name":row['name'],"item":canonical or '/p/'+row['slug']}]}
                    ld_json=json.dumps([ld,breadcrumbs],ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
                    canon=f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ''
                    photo=f'<img src="{esc(image or (row["image_path"] or "/assets/product-fallback.svg"))}" alt="{esc(row["name"])}" onerror="this.onerror=null;this.src=\'/assets/product-fallback.svg\'">'
                    rating=(f"{row['rating_average']} / 5 · {row['rating_count']} đánh giá đã duyệt" if row['rating_count'] else 'Chưa có đánh giá được duyệt')
                    condition_raw=row['condition'] or 'Chưa cập nhật'
                    for prefix in ('Đã qua sử dụng · ','Đã qua sử dụng - ','Tái chế · ','Sản phẩm tái chế · '):
                        if condition_raw.casefold().startswith(prefix.casefold()): condition_raw=condition_raw[len(prefix):]; break
                    condition=esc(condition_raw)
                    item_type_label='Đã qua sử dụng' if row['item_type']=='used' else 'Sản phẩm tái chế'
                    seller_type_label='Cá nhân' if row['seller_type']=='c2c' else 'Cửa hàng/doanh nghiệp' if row['seller_type']=='b2c' else 'Người bán ReLoop Market'
                    rating_html=f'<span class="seo-rating">★ {esc(row["rating_average"])} <small>({row["rating_count"]} đánh giá)</small></span>' if row['rating_count'] else '<span class="seo-rating-empty">Chưa có đánh giá</span>'
                    stock_label='Còn hàng' if row['stock']>0 else 'Tạm hết hàng'
                    policy=row['shipping_policy'] or 'Phí giao hàng được tính tại bước thanh toán theo khối lượng đơn hàng.'
                    body=f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(row["name"])} — ReLoop Market</title><meta name="description" content="{esc(desc[:155])}">{canon}<meta property="og:type" content="product"><meta property="og:title" content="{esc(row["name"])} — ReLoop Market"><meta property="og:description" content="{esc(desc[:155])}"><meta property="og:image" content="{esc(image)}"><meta name="robots" content="index,follow"><link rel="stylesheet" href="/styles.css"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap" rel="stylesheet"><script type="application/ld+json">{ld_json}</script><style>
                    .seo-page{{min-height:100vh;background:#f6f7f2;color:#1c2b21;font-family:'DM Sans',Arial,sans-serif}}.seo-top{{height:76px;background:#fff;border-bottom:1px solid #e8ece4;display:flex;align-items:center;justify-content:space-between;padding:0 max(5vw,24px)}}.seo-brand{{display:flex;align-items:center;gap:11px;font-weight:700;font-size:20px;letter-spacing:-.7px}}.seo-mark{{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:#28583d;color:#fff;font-size:25px}}.seo-brand small{{display:block;font-size:8px;letter-spacing:1.5px;color:#829184}}.seo-top a:last-child{{color:#315f40;font-size:13px;font-weight:600}}.seo-wrap{{max-width:1240px;margin:0 auto;padding:28px 28px 72px}}.seo-crumb{{font-size:13px;color:#77837a;margin:0 0 20px}}.seo-crumb a:hover{{color:#28583d}}.seo-card{{display:grid;grid-template-columns:minmax(0,1.02fr) minmax(0,.98fr);gap:clamp(30px,5vw,70px);padding:clamp(24px,4vw,48px);border:1px solid #e5eae1;border-radius:20px;background:#fff;box-shadow:0 14px 45px #2033220b}}.seo-gallery{{position:relative;min-height:470px;overflow:hidden;border-radius:14px;background:linear-gradient(145deg,#f0f3eb,#e9eee2);display:grid;place-items:center}}.seo-gallery img{{display:block;width:100%;height:100%;min-height:470px;max-height:590px;object-fit:cover}}.seo-gallery img[src$="product-fallback.svg"]{{object-fit:contain;padding:12%}}.seo-copy{{padding:8px 0;align-self:center}}.seo-tags{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}}.seo-tag{{display:inline-flex;align-items:center;padding:7px 11px;border-radius:30px;background:#edf4e9;color:#315f40;font-size:11px;font-weight:700}}.seo-tag.condition{{background:#f5f2e9;color:#776543}}.seo-copy h1{{font:600 clamp(32px,4vw,48px)/1.12 'Playfair Display',Georgia,serif;letter-spacing:-.8px;margin:0 0 14px;color:#17251c}}.seo-desc{{font-size:15px;line-height:1.8;color:#67746a;margin:0 0 22px;max-width:540px}}.seo-price{{font-size:32px;font-weight:700;letter-spacing:-.6px;color:#28583d;margin:0 0 18px}}.seo-meta{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:16px 0;border-top:1px solid #edf0eb;border-bottom:1px solid #edf0eb;font-size:13px;color:#556359}}.seo-rating{{color:#986b13;font-weight:700}}.seo-rating-empty{{color:#7c887f}}.seo-rating small{{color:#77837a;font-weight:500}}.seo-facts{{display:grid;grid-template-columns:1fr 1fr;gap:15px;padding:20px 0}}.seo-fact span{{display:block;color:#89938b;font-size:11px;margin-bottom:5px}}.seo-fact b{{font-size:13px;color:#26372c}}.seo-shipping{{padding:14px 16px;border-radius:10px;background:#f6f8f3;color:#5e6d61;font-size:12px;line-height:1.65;margin:0 0 23px}}.seo-actions{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}.seo-buy{{display:inline-flex;justify-content:center;align-items:center;min-height:48px;padding:0 23px;border-radius:8px;background:#28583d;color:#fff!important;font-size:13px;font-weight:700;box-shadow:0 5px 14px #28583d25;transition:background .2s,transform .2s}}.seo-buy:hover{{background:#1f4932;transform:translateY(-1px)}}.seo-back{{font-size:13px;font-weight:600;color:#536358!important}}.seo-trust{{display:flex;gap:24px;margin-top:22px;color:#7e8a80;font-size:11px}}.seo-trust span:before{{content:'✓';color:#4f8059;font-weight:700;margin-right:6px}}@media(max-width:760px){{.seo-top{{height:64px;padding:0 18px}}.seo-wrap{{padding:18px 14px 40px}}.seo-card{{grid-template-columns:1fr;gap:22px;padding:16px;border-radius:14px}}.seo-gallery,.seo-gallery img{{min-height:300px;max-height:420px}}.seo-copy{{padding:2px 3px 8px}}.seo-copy h1{{font-size:34px}}.seo-price{{font-size:28px}}.seo-trust{{gap:12px;flex-wrap:wrap}}}}@media(max-width:420px){{.seo-facts{{grid-template-columns:1fr 1fr}}.seo-meta{{gap:8px}}.seo-gallery,.seo-gallery img{{min-height:250px}}}}
                    </style></head><body class="seo-page"><header class="seo-top"><a class="seo-brand" href="/"><span class="seo-mark">↻</span><span>reloop<span style="font-weight:400;color:#7c897e">market</span><small>MUA BÁN TUẦN HOÀN</small></span></a><a href="/#products">Khám phá sản phẩm&nbsp; →</a></header><main class="seo-wrap"><nav class="seo-crumb" aria-label="Breadcrumb"><a href="/">Trang chủ</a> &nbsp;›&nbsp; <a href="/#products">{esc(row["category"])}</a> &nbsp;›&nbsp; <span>{esc(row["name"])}</span></nav><article class="seo-card"><div class="seo-gallery">{photo}</div><div class="seo-copy"><div class="seo-tags"><span class="seo-tag">{esc(item_type_label)}</span><span class="seo-tag condition">{condition}</span></div><h1>{esc(row["name"])}</h1><p class="seo-desc">{esc(desc)}</p><p class="seo-price">{format(row["price"],",")}đ</p><div class="seo-meta">{rating_html}<span>·</span><span>{esc(stock_label)}</span></div><div class="seo-facts"><div class="seo-fact"><span>Người bán</span><b>{esc(row["seller"])}</b></div><div class="seo-fact"><span>Hình thức</span><b>{esc(seller_type_label)}</b></div><div class="seo-fact"><span>Danh mục</span><b>{esc(row["category"])}</b></div><div class="seo-fact"><span>Tình trạng</span><b>{condition}</b></div></div><p class="seo-shipping">{esc(policy)}</p><div class="seo-actions"><a class="seo-buy" href="/?add={esc(row["id"])}">Xem và mua sản phẩm&nbsp; →</a><a class="seo-back" href="/#products">Quay lại cửa hàng</a></div><div class="seo-trust"><span>Giao dịch có thông tin rõ ràng</span><span>Mua bán tuần hoàn</span></div></div></article></main></body></html>'''
                    body=body.replace(
                        "</article></main></body></html>",
                        f'</article><section id="productRecommendations" class="section recommendation-section hidden" data-recommendation-context="product" data-recommendation-root="true" data-product-id="{esc(row["id"])}" aria-labelledby="productRecommendationsTitle"><div class="section-head"><div><div class="eyebrow">CÙNG KHÁM PHÁ</div><h2 id="productRecommendationsTitle">Sản phẩm tương tự</h2></div></div><div class="recommendation-status" role="status" aria-live="polite"></div><div class="product-grid recommendation-grid"></div></section></main><div id="toast" class="toast" role="status" aria-live="polite"></div><script src="/recommendations.js"></script></body></html>')
                    return self.send_bytes(200,body.encode(),"text/html; charset=utf-8")
                if path not in ("/", "/index.html", "/styles.css", "/app.js", "/ux.js", "/recommendations.js", "/policies.html", "/policies.js", "/guides.html", "/robots.txt", "/assets/interior.svg", "/assets/fashion.svg", "/assets/electronics.svg", "/assets/homeware.svg", "/assets/recycled.svg", "/assets/product-fallback.svg", "/assets/vnpay-personal-qr.jpg") and not re.fullmatch(r"/assets/uploads/[a-f0-9]{32}\.(?:png|jpg|webp)",path):
                    return self.serve_404()
                return super().do_GET()
            with connect() as db:
                if path=="/api/products":
                    query=parse_qs(urlparse(self.path).query); clauses=["p.status='approved'","p.lifecycle_status='active'"]; params=[]
                    term=query.get('q',[''])[0].strip()[:100]
                    if term: clauses.append("(p.name LIKE ? OR p.description LIKE ? OR p.seller LIKE ?)"); params.extend([f'%{term}%']*3)
                    cat=query.get('category',[''])[0].strip()
                    if cat:
                        clauses.append("(p.category=? OR c.name=? OR c.slug=? OR c.id IN (WITH RECURSIVE tree(id) AS (SELECT id FROM categories WHERE slug=? UNION ALL SELECT c2.id FROM categories c2 JOIN tree t ON c2.parent_id=t.id) SELECT id FROM tree))"); params.extend([cat,cat,cat,cat])
                    for key,col,op in [('min_price','p.price','>='),('max_price','p.price','<='),('condition','p.condition','LIKE'),('item_type','p.item_type','='),('seller','p.seller','LIKE')]:
                        value=query.get(key,[''])[0].strip()
                        if value:
                            clauses.append(f"{col} {op} ?"); params.append(f'%{value}%' if op=='LIKE' else value)
                    rentable=query.get('rentable',[''])[0]
                    if rentable in ('1','0'): clauses.append('p.rentable=?'); params.append(int(rentable))
                    seller_type=query.get('seller_type',[''])[0]
                    if seller_type in ('c2c','b2c'): clauses.append("EXISTS(SELECT 1 FROM seller_profiles sp WHERE sp.user_id=p.owner_id AND sp.status='approved' AND sp.business_type=?)"); params.append(seller_type)
                    where=' AND '.join(clauses); sort=query.get('sort',['relevance'])[0]
                    order={'price-asc':'p.price ASC','price-desc':'p.price DESC','newest':'p.created_at DESC','relevance':'p.created_at DESC'}.get(sort,'p.created_at DESC')
                    try: page=max(1,int(query.get('page',['1'])[0])); per_page=min(48,max(1,int(query.get('per_page',['12'])[0])))
                    except ValueError: raise APIError(400,"Trang phân trang không hợp lệ")
                    count=db.execute(f"SELECT COUNT(*) FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE {where}",params).fetchone()[0]
                    rows=db.execute(f"SELECT p.id,p.name,p.slug,p.short_description,p.description,p.specifications_json,p.category,p.condition,p.seller,p.seller_type,p.price,p.emoji,p.bg,p.badge,p.co2,p.rentable AS rent,p.stock,p.item_type,p.rental_price_day,p.lifecycle_status,p.shipping_policy,p.return_policy,p.weight_grams,(SELECT image_path FROM product_images i WHERE i.product_id=p.id ORDER BY i.sort_order,i.id LIMIT 1) image_path FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",(*params,per_page,(page-1)*per_page)).fetchall()
                    if not query:return self.send_json(200,[dict(r) for r in rows])
                    return self.send_json(200,{"items":[dict(r) for r in rows],"page":page,"per_page":per_page,"total":count,"pages":(count+per_page-1)//per_page})
                if path=="/api/categories":
                    rows=db.execute("SELECT id,name,slug,parent_id,sort_order FROM categories WHERE is_active=1 ORDER BY COALESCE(parent_id,id),sort_order,name").fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path.startswith('/api/products/') and path.endswith('/reviews'):
                    pid=path.split('/')[-2]; stats=db.execute("SELECT ROUND(AVG(rating),1) average,COUNT(*) count FROM reviews WHERE product_id=? AND status='approved' AND is_demo=0",(pid,)).fetchone(); reviews=[dict(r) for r in db.execute("SELECT r.rating,r.body,r.seller_reply,r.created_at,r.is_demo,u.name reviewer FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.product_id=? AND r.status='approved' ORDER BY r.created_at DESC LIMIT 50",(pid,)).fetchall()]; return self.send_json(200,{"average":stats['average'] or 0,"count":stats['count'],"items":reviews})
                if path=="/api/recommendations":
                    query=parse_qs(urlparse(self.path).query)
                    context=query.get('context',['home'])[0]
                    if context not in ('home','cart'): raise APIError(400,"Ngữ cảnh gợi ý không hợp lệ")
                    try: limit=int(query.get('limit',['8'])[0])
                    except ValueError: raise APIError(400,"Số lượng gợi ý không hợp lệ")
                    limit=max(1,min(12,limit))
                    cart_ids=[]
                    if context=='cart':
                        cart_ids=[value.strip() for value in query.get('cart',[''])[0].split(',') if value.strip() and len(value.strip())<=120][:20]
                    result=recommend_products(db,self.current_user(),context,cart_ids=cart_ids,limit=limit)
                    return self.send_json(200,result)
                if path.startswith('/api/recommendations/'):
                    pid=path.rsplit('/',1)[-1]
                    result=recommend_products(db,self.current_user(),"product",product_id=pid,limit=6)
                    return self.send_json(200,result)
                if path=="/api/impact":
                    completed=db.execute("SELECT COUNT(*) orders,COALESCE(SUM(total),0) revenue FROM orders WHERE status='Hoàn tất' AND payment='COD' AND is_demo=0").fetchone(); metrics=db.execute("SELECT COALESCE(SUM(CASE WHEN p.item_type='used' THEN oi.quantity ELSE 0 END),0) used_items,COALESCE(SUM(CASE WHEN p.item_type='recycled' THEN oi.quantity ELSE 0 END),0) recycled_items FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id WHERE o.status='Hoàn tất' AND o.is_demo=0").fetchone(); points=db.execute("SELECT COALESCE(SUM(pl.points),0) FROM points_ledger pl WHERE pl.points>0 AND NOT EXISTS(SELECT 1 FROM orders o WHERE o.id=pl.reference_id AND pl.reference_type='order' AND o.is_demo=1)").fetchone()[0]
                    snapshots=db.execute("SELECT COALESCE(SUM(estimated_value),0) total,COUNT(*) n,MIN(unit) unit FROM impact_snapshots s JOIN order_items oi ON oi.id=s.order_item_id JOIN orders o ON o.id=oi.order_id WHERE o.status='Hoàn tất'").fetchone()
                    return self.send_json(200,{"completed_orders":completed['orders'],"revenue":completed['revenue'],"co2_kg":snapshots['total'] if snapshots['n'] else None,"impact_unit":snapshots['unit'] if snapshots['n'] else None,"impact_configured":bool(snapshots['n']),"items_reused":metrics['used_items'],"items_recycled":metrics['recycled_items'],"points_awarded":points})
                if path.startswith('/api/products/'):
                    pid=path.rsplit('/',1)[-1]; row=db.execute("SELECT id,name,slug,short_description,category,condition,seller,seller_type,price,emoji,bg,badge,rentable AS rent,description,specifications_json,shipping_policy,return_policy,lifecycle_status,owner_id,stock,rental_price_day,item_type,weight_grams,(SELECT image_path FROM product_images i WHERE i.product_id=products.id ORDER BY i.sort_order,i.id LIMIT 1) image_path FROM products WHERE id=? AND status='approved' AND lifecycle_status='active'",(pid,)).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy sản phẩm")
                    result=dict(row); result.pop('owner_id',None); result['images']=[dict(i) for i in db.execute("SELECT image_path,alt_text,sort_order FROM product_images WHERE product_id=? ORDER BY sort_order,id",(pid,)).fetchall()]; stats=db.execute("SELECT ROUND(AVG(rating),1) average,COUNT(*) count FROM reviews WHERE product_id=? AND status='approved' AND is_demo=0",(pid,)).fetchone(); result['rating_average']=stats['average'] or 0; result['rating_count']=stats['count']; assessment=db.execute("SELECT appearance_score,functionality,wear_level,accessories,usage_years,score,recycled_material_pct FROM product_condition_assessments WHERE product_id=?",(pid,)).fetchone(); result['condition_assessment']=dict(assessment) if assessment else None
                    if row['owner_id']:
                        profile=db.execute("SELECT sp.user_id,sp.business_type,sp.display_name,sp.description FROM seller_profiles sp WHERE sp.user_id=? AND sp.status='approved'",(row['owner_id'],)).fetchone()
                        result['seller_profile']=dict(profile) if profile else None
                    return self.send_json(200,result)
                if path.startswith('/api/sellers/'):
                    sid=path.rsplit('/',1)[-1]
                    profile=db.execute("SELECT sp.user_id,sp.business_type,sp.display_name,sp.description FROM seller_profiles sp WHERE sp.user_id=? AND sp.status='approved'",(sid,)).fetchone()
                    if not profile: raise APIError(404,"Không tìm thấy hồ sơ người bán")
                    result=dict(profile); result['products']=[dict(r) for r in db.execute("SELECT id,name,slug,category,condition,seller,price,emoji,bg,badge,rentable AS rent FROM products WHERE owner_id=? AND status='approved' AND lifecycle_status='active' ORDER BY created_at DESC",(sid,)).fetchall()]
                    return self.send_json(200,result)
                if path=="/api/me":
                    user=self.current_user();
                    if not user:return self.send_json(200,{"user":None,"points":0})
                    points=db.execute("SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE user_id=?",(user['id'],)).fetchone()[0]
                    return self.send_json(200,{"user":user,"points":points})
                if path=="/api/payment-options":
                    cfg=vnpay_settings(); configured=all(cfg[k] for k in ("tmn_code","hash_secret","return_url","ipn_url"))
                    return self.send_json(200,{"methods":["COD","VNPAY_QR"]+(["VNPAY"] if configured else []),"vnpay_configured":configured,"qr_transfer_enabled":True,"provider":"VNPay sandbox + QR transfer thủ công"})
                if path=="/api/orders":
                    user=self.current_user(True); db.execute('BEGIN IMMEDIATE'); expire_vnpay_orders(db); orders=db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",(user['id'],)).fetchall(); return self.send_json(200,[self.order_json(db,o) for o in orders])
                if path.startswith('/api/payment-status/'):
                    user=self.current_user(True); db.execute('BEGIN IMMEDIATE'); expire_vnpay_orders(db); oid=path.rsplit('/',1)[-1]; order=db.execute("SELECT id,payment,payment_status,total,status FROM orders WHERE id=? AND user_id=?",(oid,user['id'])).fetchone()
                    if not order: raise APIError(404,"Không tìm thấy đơn hàng")
                    history=[dict(r) for r in db.execute("SELECT payment_status,source,note,created_at FROM payment_status_history WHERE order_id=? ORDER BY created_at,id",(oid,)).fetchall()]
                    return self.send_json(200,{**dict(order),"history":history})
                if path=="/api/points/history":
                    user=self.current_user(True); rows=db.execute("SELECT id,points,event_type,reference_type,reference_id,note,created_at FROM points_ledger WHERE user_id=? ORDER BY created_at DESC,id DESC",(user['id'],)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/addresses":
                    user=self.current_user(True); return self.send_json(200,[dict(r) for r in db.execute("SELECT id,recipient,phone,address,is_default FROM addresses WHERE user_id=? ORDER BY is_default DESC,id DESC",(user['id'],)).fetchall()])
                if path=="/api/favorites":
                    user=self.current_user(True); return self.send_json(200,[dict(r) for r in db.execute("SELECT p.id,p.name,p.category,p.price,p.emoji,p.bg,p.badge,p.condition,p.seller,p.stock,p.rentable AS rent,p.lifecycle_status FROM favorites f JOIN products p ON p.id=f.product_id WHERE f.user_id=? AND p.status='approved'",(user['id'],)).fetchall()])
                if path=="/api/seller/products":
                    user=self.require_role('seller'); rows=[dict(r) for r in db.execute("SELECT * FROM products WHERE owner_id=? ORDER BY updated_at DESC,created_at DESC",(user['id'],)).fetchall()]
                    for row in rows:
                        row['images']=[dict(i) for i in db.execute("SELECT image_path,alt_text,sort_order FROM product_images WHERE product_id=? ORDER BY sort_order,id",(row['id'],)).fetchall()]
                        score=db.execute("SELECT appearance_score,functionality,wear_level,accessories,usage_years,score,recycled_material_pct FROM product_condition_assessments WHERE product_id=?",(row['id'],)).fetchone(); row['condition_assessment']=dict(score) if score else None
                    return self.send_json(200,rows)
                if path.startswith('/api/seller/products/') and path.endswith('/history'):
                    user=self.require_role('seller'); pid=path.split('/')[-2]
                    if not db.execute("SELECT 1 FROM products WHERE id=? AND owner_id=?",(pid,user['id'])).fetchone(): raise APIError(404,"Không tìm thấy sản phẩm thuộc cửa hàng của bạn")
                    rows=db.execute("SELECT action,snapshot_json,created_at FROM product_history WHERE product_id=? ORDER BY created_at DESC,id DESC",(pid,)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/seller/orders":
                    user=self.require_role('seller'); rows=db.execute("SELECT oi.id item_id,oi.order_id,oi.product_id,oi.name,oi.price,oi.quantity,oi.rental_days,oi.fulfillment_status,CASE WHEN o.kind='rental' AND COALESCE(o.total,0)=0 THEN oi.price*oi.quantity*COALESCE(oi.rental_days,1) ELSE o.total END order_total,o.kind,o.payment,o.payment_status,o.status order_status,o.created_at,o.address,o.is_demo,u.name customer_name,rr.start_date,rr.end_date,rr.status rental_status FROM order_items oi JOIN products p ON p.id=oi.product_id JOIN orders o ON o.id=oi.order_id JOIN users u ON u.id=o.user_id LEFT JOIN rental_reservations rr ON rr.order_id=o.id AND rr.product_id=p.id WHERE p.owner_id=? ORDER BY o.created_at DESC",(user['id'],)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/orders":
                    self.current_user(True,True); db.execute('BEGIN IMMEDIATE'); expire_vnpay_orders(db); orders=db.execute("SELECT o.*,u.name customer_name FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created_at DESC").fetchall(); return self.send_json(200,[self.order_json(db,o) for o in orders])
                if path=="/api/admin/products":
                    self.current_user(True,True); rows=db.execute("SELECT p.*,pc.score condition_score,pc.recycled_material_pct FROM products p LEFT JOIN product_condition_assessments pc ON pc.product_id=p.id WHERE p.status='pending' AND p.lifecycle_status='pending_review' ORDER BY p.created_at").fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/sellers":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT sp.*,u.name,u.email FROM seller_profiles sp JOIN users u ON u.id=sp.user_id ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END,created_at DESC").fetchall()])
                if path=="/api/admin/users":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()])
                if path=="/api/admin/audit":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 200").fetchall()])
                if path=="/api/admin/security-events":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT id,event_type,user_id,created_at FROM security_events ORDER BY created_at DESC LIMIT 200").fetchall()])
                if path=="/api/site-info":
                    return self.send_json(200,{"brand":"ReLoop Market","policy_version":POLICY_VERSION,"operator":{key:os.environ.get(env_key,"").strip() for key,env_key in PUBLIC_SITE_FIELDS.items()},"demo_mode":os.environ.get('RELOOP_ENV','development').lower()!='production'})
                if path=="/api/privacy-requests":
                    user=self.current_user(True); rows=db.execute("SELECT id,request_type,details,status,resolution_note,created_at,updated_at FROM privacy_requests WHERE user_id=? ORDER BY created_at DESC",(user['id'],)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/privacy-requests":
                    self.current_user(True,True); rows=db.execute("SELECT r.id,r.user_id,u.name,u.email,r.request_type,r.details,r.status,r.resolution_note,r.created_at,r.updated_at FROM privacy_requests r JOIN users u ON u.id=r.user_id ORDER BY CASE r.status WHEN 'pending' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END,r.created_at").fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/support-requests":
                    user=self.current_user(True); rows=db.execute("SELECT id,order_id,category,subject,details,status,admin_note,created_at,updated_at FROM support_requests WHERE user_id=? ORDER BY created_at DESC",(user['id'],)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/support-requests":
                    self.current_user(True,True); rows=db.execute("SELECT r.*,u.name customer_name,u.email customer_email FROM support_requests r JOIN users u ON u.id=r.user_id ORDER BY CASE r.status WHEN 'pending' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END,r.created_at").fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/categories":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT id,name,slug,parent_id,sort_order,is_active FROM categories ORDER BY COALESCE(parent_id,id),sort_order").fetchall()])
                if path=="/api/admin/reviews":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT r.*,u.name reviewer,p.name product_name FROM reviews r JOIN users u ON u.id=r.user_id JOIN products p ON p.id=r.product_id ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END,r.created_at DESC").fetchall()])
                if path=="/api/admin/vouchers":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT * FROM vouchers ORDER BY created_at DESC").fetchall()])
                if path=="/api/admin/notifications":
                    self.current_user(True,True); return self.send_json(200,[dict(r) for r in db.execute("SELECT id,user_id,kind,subject,status,error,created_at,sent_at FROM notification_outbox ORDER BY created_at DESC LIMIT 200").fetchall()])
                if path=="/api/seller/profile":
                    user=self.current_user(True); row=db.execute("SELECT business_type,display_name,description,status,created_at FROM seller_profiles WHERE user_id=?",(user['id'],)).fetchone(); return self.send_json(200,dict(row) if row else {"status":"none"})
                if path=="/api/admin/overview":
                    self.current_user(True,True); return self.send_json(200,{"orders":db.execute("SELECT COUNT(*) FROM orders WHERE is_demo=0").fetchone()[0],"products":db.execute("SELECT COUNT(*) FROM products WHERE status='approved'").fetchone()[0],"pending":db.execute("SELECT COUNT(*) FROM products WHERE status='pending'").fetchone()[0],"pending_orders":db.execute("SELECT COUNT(*) FROM orders WHERE status='Đang xử lý' AND is_demo=0").fetchone()[0],"revenue":db.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status='Hoàn tất' AND payment='COD' AND is_demo=0").fetchone()[0],"co2":db.execute("SELECT COALESCE(SUM(s.estimated_value),0) FROM impact_snapshots s JOIN order_items oi ON oi.id=s.order_item_id JOIN orders o ON o.id=oi.order_id WHERE o.status='Hoàn tất' AND o.is_demo=0").fetchone()[0],"impact_configured":bool(db.execute("SELECT COUNT(*) FROM impact_factors WHERE active=1").fetchone()[0]),"customers":db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0],"sellers":db.execute("SELECT COUNT(*) FROM users WHERE role='seller'").fetchone()[0],"revenue_by_day":[dict(r) for r in db.execute("SELECT date(created_at,'unixepoch') day,SUM(total) revenue FROM orders WHERE status='Hoàn tất' AND payment='COD' AND is_demo=0 GROUP BY day ORDER BY day DESC LIMIT 30").fetchall()]})
                if path=="/api/subscriptions":
                    user=self.current_user(True); rows=db.execute("SELECT id,plan,price,status,cadence,starts_at,next_due_at,cancelled_at,created_at FROM subscriptions WHERE user_id=? ORDER BY id DESC",(user['id'],)).fetchall(); return self.send_json(200,[dict(r) for r in rows])
                if path=="/api/admin/impact-factors":
                    self.current_user(True,True); rows=db.execute("SELECT * FROM impact_factors ORDER BY item_type,version DESC").fetchall(); return self.send_json(200,[dict(r) for r in rows])
            raise APIError(404,"Không tìm thấy API")
        except APIError as e:self.send_json(e.status,{"error":e.message})
        except Exception as e: print("API error:",repr(e)); self.send_json(500,{"error":"Lỗi máy chủ"})

    def order_json(self,db,o):
        items=db.execute("SELECT product_id id,name,price,quantity qty,rental_days FROM order_items WHERE order_id=?",(o['id'],)).fetchall()
        result={k:o[k] for k in o.keys()}; result['items']=[dict(i) for i in items]
        # Rental bookings created by older builds could have a zero order total.
        # Derive a display total from the immutable order-line snapshot without rewriting history.
        if result.get('kind')=='rental' and not result.get('total'):
            result['total']=sum(int(i['price'] or 0)*int(i['qty'] or 1)*int(i['rental_days'] or 1) for i in result['items'])
        if result.get('kind')=='rental':
            rental=db.execute("SELECT start_date,end_date,status,deposit_amount FROM rental_reservations WHERE order_id=? ORDER BY id LIMIT 1",(o['id'],)).fetchone()
            result['rental']=dict(rental) if rental else None
        result['status_history']=[dict(h) for h in db.execute("SELECT status,note,created_at FROM order_status_history WHERE order_id=? ORDER BY created_at,id",(o['id'],)).fetchall()]; return result

    def do_POST(self): self.route_mutation("POST")
    def do_PUT(self): self.route_mutation("PUT")
    def route_mutation(self,method):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):
            self.send_json(404,{"error":"Không tìm thấy"});return
        try:
            self.check_origin(require_origin=bool(self.cookies().get(COOKIE))); data=self.read_json(4_200_000 if path=="/api/uploads/product-image" else 32_000)
            if method=="POST" and path in ("/api/register","/api/login"):
                email=str(data.get('email','')).strip().lower(); password=data.get('password',''); name=str(data.get('name','')).strip()
                if not isinstance(password,str) or len(password.encode('utf-8'))>128 or (path.endswith('register') and (len(password)<12 or len(password.encode('utf-8'))>72)): raise APIError(400,"Mật khẩu mới cần từ 12 ký tự và tối đa 72 byte UTF-8")
                if len(email)>254 or (path.endswith('register') and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)): raise APIError(400,"Email không hợp lệ")
                with connect() as db:
                    if path.endswith('register'):
                        if not name or len(name)>100: raise APIError(400,"Tên không hợp lệ")
                        try: cur=db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",(name,email,password_hash(password),'customer',int(time.time())))
                        except sqlite3.IntegrityError: raise APIError(409,"Email đã được đăng ký")
                        uid=cur.lastrowid
                    else:
                        now=int(time.time()); ip_hash=hashlib.sha256(self.client_address[0].encode()).hexdigest(); account_hash=hashlib.sha256(email.encode()).hexdigest()
                        db.execute('BEGIN IMMEDIATE')
                        blocked=max(self.login_bucket_state(db,'ip:'+ip_hash,20,now),self.login_bucket_state(db,'account:'+account_hash,8,now))
                        if blocked>now:
                            self.audit_security(db,'login.throttled',ip_hash,account_hash)
                            return self.send_json(429,{"error":"Đăng nhập tạm thời bị giới hạn. Vui lòng thử lại sau."},{"Retry-After":str(blocked-now)})
                        row=db.execute("SELECT id,password_hash FROM users WHERE email=? COLLATE NOCASE",(email,)).fetchone()
                        valid=password_matches(password,row['password_hash']) if row else bcrypt.checkpw(password.encode()[:72],DUMMY_PASSWORD_HASH)
                        if not valid:
                            self.record_login_failure(db,ip_hash,account_hash,now)
                            return self.send_json(401,{"error":"Email hoặc mật khẩu không đúng"})
                        uid=row['id']
                        db.execute("DELETE FROM login_attempt_buckets WHERE bucket_key IN (?,?)",('ip:'+ip_hash,'account:'+account_hash))
                        self.audit_security(db,'login.success',ip_hash,account_hash,uid)
                        if password_needs_rehash(row['password_hash']) and len(password.encode('utf-8'))<=72:
                            db.execute("UPDATE users SET password_hash=? WHERE id=?",(password_hash(password),uid))
                    token=secrets.token_urlsafe(32); db.execute("INSERT INTO sessions VALUES(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+SESSION_SECONDS))
                    user=dict(db.execute("SELECT id,name,email,role FROM users WHERE id=?",(uid,)).fetchone())
                    return self.send_json(200,{"user":user},{"Set-Cookie":f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}{COOKIE_SECURE_ATTRIBUTE}"})
            if method=="POST" and path=="/api/logout":
                token=self.cookies().get(COOKIE)
                if token:
                    with connect() as db: db.execute("DELETE FROM sessions WHERE token_hash=?",(hashlib.sha256(token.encode()).hexdigest(),))
                return self.send_json(200,{"ok":True},{"Set-Cookie":f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0{COOKIE_SECURE_ATTRIBUTE}"})
            if method=="POST" and path=="/api/password/change":
                user=self.current_user(True); old=data.get('current_password',''); new=data.get('new_password','')
                if not isinstance(old,str) or not isinstance(new,str) or len(new)<12 or len(new.encode('utf-8'))>72: raise APIError(400,"Mật khẩu mới cần ít nhất 12 ký tự và tối đa 72 byte UTF-8")
                with connect() as db:
                    row=db.execute("SELECT password_hash FROM users WHERE id=?",(user['id'],)).fetchone()
                    if not password_matches(old,row['password_hash']): raise APIError(403,"Mật khẩu hiện tại không đúng")
                    current_token=self.cookies().get(COOKIE,''); current_hash=hashlib.sha256(current_token.encode()).hexdigest()
                    db.execute("UPDATE users SET password_hash=? WHERE id=?",(password_hash(new),user['id']))
                    db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?",(user['id'],current_hash))
                    self.audit_security(db,'password.changed',user_id=user['id'])
                    self.audit(db,user,'security.password_change','user',user['id'])
                return self.send_json(200,{"ok":True,"message":"Đã đổi mật khẩu; các phiên khác đã đăng xuất"})
            if method=="POST" and path=="/api/uploads/product-image":
                user=self.require_role('seller')
                with connect() as db:
                    profile=db.execute("SELECT status FROM seller_profiles WHERE user_id=?",(user['id'],)).fetchone()
                    if not profile or profile['status']!='approved': raise APIError(403,"Hồ sơ người bán cần được duyệt trước khi tải ảnh")
                mime=data.get('mime_type'); encoded=data.get('data_base64')
                extensions={'image/png':('png',b'\x89PNG\r\n\x1a\n'),'image/jpeg':('jpg',b'\xff\xd8\xff'),'image/webp':('webp',b'RIFF')}
                if mime not in extensions or not isinstance(encoded,str) or len(encoded)>4_000_000: raise APIError(400,"Chỉ chấp nhận PNG, JPEG hoặc WebP, tối đa 3 MB")
                try: content=base64.b64decode(encoded,validate=True)
                except (ValueError,binascii.Error): raise APIError(400,"Dữ liệu ảnh không hợp lệ")
                extension,signature=extensions[mime]
                if not content or len(content)>3_000_000 or not content.startswith(signature) or (mime=='image/webp' and content[8:12]!=b'WEBP'): raise APIError(400,"Tệp không đúng định dạng khai báo hoặc vượt quá 3 MB")
                with connect() as db:
                    recent=db.execute("SELECT COUNT(*) FROM upload_assets WHERE owner_id=? AND created_at>?",(user['id'],int(time.time())-86400)).fetchone()[0]
                    if recent>=50: raise APIError(429,"Đã đạt giới hạn 50 ảnh tải lên trong 24 giờ")
                    UPLOAD_DIR.mkdir(parents=True,exist_ok=True); filename=secrets.token_hex(16)+'.'+extension; relative='/assets/uploads/'+filename
                    with (UPLOAD_DIR/filename).open('xb') as target: target.write(content)
                    db.execute("INSERT INTO upload_assets(path,owner_id,mime_type,size,created_at) VALUES(?,?,?,?,?)",(relative,user['id'],mime,len(content),int(time.time())))
                return self.send_json(201,{"path":relative,"size":len(content),"mime_type":mime})
            if method=="PUT" and path.startswith('/api/seller/products/'):
                actor=self.require_role('seller'); pid=path.rsplit('/',1)[-1]
                name=safe_product_text(data.get('name',''),100,'Tên sản phẩm'); category=str(data.get('category','')); condition=safe_product_text(data.get('condition',''),100,'Tình trạng'); weight_kg=data.get('weight_kg',1)
                description=safe_product_text(data.get('description',''),5000,'Mô tả'); short=safe_product_text(data.get('short_description',description[:180]),180,'Mô tả ngắn')
                price=data.get('price'); stock=data.get('stock'); slug=slugify(safe_product_text(data.get('slug',''),120,'Slug') or name)
                specs=data.get('specifications',{}); images=data.get('image_paths')
                if category not in ('Nội thất','Thời trang','Điện tử','Đồ gia dụng','Tái chế') or not isinstance(price,int) or price<1000 or price>1_000_000_000 or not isinstance(stock,int) or stock<0 or not isinstance(weight_kg,(int,float)) or isinstance(weight_kg,bool) or not 0<weight_kg<=1000 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug): raise APIError(400,"Tên, danh mục, slug, giá, tồn kho hoặc khối lượng không hợp lệ")
                if not isinstance(specs,dict) or len(specs)>30 or len(json.dumps(specs,ensure_ascii=False))>5000: raise APIError(400,"Thông số sản phẩm không hợp lệ")
                shipping=safe_product_text(data.get('shipping_policy',''),500,'Chính sách giao hàng'); returns=safe_product_text(data.get('return_policy',''),500,'Chính sách đổi trả')
                appearance=data.get('appearance_score',80); functionality=data.get('functionality','working'); wear=data.get('wear_level','medium'); accessories=data.get('accessories','complete'); years=data.get('usage_years',0); recycled_pct=data.get('recycled_material_pct')
                rentable=data.get('rentable',False); rental_price=data.get('rental_price_day',0); rental_stock=data.get('rental_stock',1)
                if not isinstance(appearance,int) or not 0<=appearance<=100 or functionality not in ('working','partial','not_working') or wear not in ('low','medium','high') or accessories not in ('complete','partial','none') or not isinstance(years,int) or not 0<=years<=50 or (recycled_pct is not None and (not isinstance(recycled_pct,int) or not 0<=recycled_pct<=100)): raise APIError(400,"Thông tin tình trạng không hợp lệ")
                if recycled_pct is not None and category!='Tái chế': raise APIError(400,"Tỷ lệ tái chế chỉ áp dụng cho danh mục Tái chế")
                if not isinstance(rentable,bool) or not isinstance(rental_price,int) or not isinstance(rental_stock,int) or rental_stock<1 or (rentable and not 1000<=rental_price<=100_000_000): raise APIError(400,"Thông tin cho thuê không hợp lệ")
                score=round(appearance*.35+{'working':100,'partial':55,'not_working':0}[functionality]*.30+{'low':100,'medium':70,'high':35}[wear]*.20+{'complete':100,'partial':60,'none':20}[accessories]*.10+max(0,100-years*5)*.05)
                with connect() as db:
                    db.execute("BEGIN IMMEDIATE"); old=db.execute("SELECT * FROM products WHERE id=? AND owner_id=?",(pid,actor['id'])).fetchone()
                    if not old: raise APIError(404,"Không tìm thấy sản phẩm thuộc cửa hàng của bạn")
                    if old['lifecycle_status']=='archived': raise APIError(409,"Sản phẩm đã lưu trữ không thể chỉnh sửa")
                    if db.execute("SELECT 1 FROM products WHERE slug=? AND id<>?",(slug,pid)).fetchone(): raise APIError(409,"Slug sản phẩm đã được sử dụng")
                    if images is None: images=[i['image_path'] for i in db.execute("SELECT image_path FROM product_images WHERE product_id=? ORDER BY sort_order,id",(pid,)).fetchall()]
                    if not isinstance(images,list) or len(images)>5: raise APIError(400,"Tối đa 5 ảnh sản phẩm")
                    previous_images={r['image_path'] for r in db.execute("SELECT image_path FROM product_images WHERE product_id=?",(pid,)).fetchall()}
                    removed_uploads=previous_images-set(images)
                    for image in images:
                        if not isinstance(image,str) or not re.fullmatch(r'/assets/uploads/[a-f0-9]{32}\.(?:png|jpg|webp)',image): raise APIError(400,"Ảnh không hợp lệ hoặc không tồn tại")
                        asset=db.execute("SELECT owner_id,product_id FROM upload_assets WHERE path=?",(image,)).fetchone()
                        already_attached=image in previous_images
                        if asset and (asset['owner_id']!=actor['id'] or asset['product_id'] not in (None,pid)): raise APIError(403,"Ảnh tải lên thuộc tài khoản hoặc sản phẩm khác")
                        if not asset and not already_attached: raise APIError(400,"Ảnh không thuộc tài khoản người bán này")
                        if asset and not (UPLOAD_DIR/image.rsplit('/',1)[-1]).is_file(): raise APIError(400,"Tệp ảnh không còn tồn tại")
                        if not asset and not (LEGACY_UPLOAD_DIR/image.rsplit('/',1)[-1]).is_file(): raise APIError(400,"Tệp ảnh cũ không còn tồn tại")
                    old_snapshot={"name":old['name'],"slug":old['slug'],"price":old['price'],"stock":old['stock'],"description":old['description'],"status":old['lifecycle_status']}; now=int(time.time())
                    db.execute("UPDATE products SET name=?,slug=?,category=?,category_id=(SELECT id FROM categories WHERE slug=CASE ? WHEN 'Điện tử' THEN 'dien-tu' WHEN 'Thời trang' THEN 'thoi-trang' WHEN 'Đồ gia dụng' THEN 'do-gia-dung' WHEN 'Nội thất' THEN 'do-gia-dung' ELSE 'san-pham-tai-che' END),item_type=?,condition=?,price=?,description=?,short_description=?,specifications_json=?,shipping_policy=?,return_policy=?,stock=?,rentable=?,rental_price_day=?,rental_stock=?,weight_grams=?,status='pending',lifecycle_status='pending_review',badge='Chờ duyệt cập nhật',updated_at=? WHERE id=? AND owner_id=?",(name,slug,category,category,'recycled' if category=='Tái chế' else 'used',condition,price,description,short,json.dumps(specs,ensure_ascii=False),shipping,returns,stock,int(rentable),rental_price if rentable else 0,rental_stock,round(weight_kg*1000),now,pid,actor['id']))
                    db.execute("DELETE FROM product_images WHERE product_id=?",(pid,)); db.execute("UPDATE upload_assets SET product_id=NULL WHERE product_id=?",(pid,))
                    db.executemany("INSERT INTO product_images(product_id,image_path,alt_text,sort_order,created_at) VALUES(?,?,?,?,?)",[(pid,p,name,i,now) for i,p in enumerate(images)])
                    db.executemany("UPDATE upload_assets SET product_id=? WHERE path=? AND owner_id=?",( (pid,p,actor['id']) for p in images))
                    db.execute("UPDATE product_condition_assessments SET appearance_score=?,functionality=?,wear_level=?,accessories=?,usage_years=?,score=?,recycled_material_pct=?,updated_at=? WHERE product_id=?",(appearance,functionality,wear,accessories,years,score,recycled_pct,now,pid))
                    db.execute("INSERT INTO product_history(product_id,actor_id,action,snapshot_json,created_at) VALUES(?,?,?,?,?)",(pid,actor['id'],'edited',json.dumps({"before":old_snapshot,"after":{"name":name,"slug":slug,"price":price,"stock":stock,"description":description}},ensure_ascii=False),now))
                for old_image in removed_uploads:
                    filename=old_image.rsplit('/',1)[-1]
                    with connect() as db:
                        asset=db.execute("SELECT id FROM upload_assets WHERE path=? AND product_id IS NULL AND owner_id=?",(old_image,actor['id'])).fetchone()
                        if asset:
                            (UPLOAD_DIR/filename).unlink(missing_ok=True)
                            db.execute("DELETE FROM upload_assets WHERE id=?",(asset['id'],))
                return self.send_json(200,{"ok":True,"lifecycle_status":"pending_review"})
            if method=="POST" and path.startswith('/api/seller/products/') and path.endswith('/lifecycle'):
                actor=self.require_role('seller'); pid=path.split('/')[-2]; action=data.get('action')
                with connect() as db:
                    db.execute("BEGIN IMMEDIATE"); product=db.execute("SELECT status,lifecycle_status,stock FROM products WHERE id=? AND owner_id=?",(pid,actor['id'])).fetchone()
                    if not product: raise APIError(404,"Không tìm thấy sản phẩm thuộc cửa hàng của bạn")
                    if action=='hide' and product['lifecycle_status']=='active': target='hidden'
                    elif action=='publish' and product['status']=='approved' and product['stock']>0: target='active'
                    elif action=='archive' and product['lifecycle_status'] in ('draft','hidden','rejected','out_of_stock'): target='archived'
                    elif action=='submit' and product['lifecycle_status'] in ('draft','rejected'): target='pending_review'
                    else: raise APIError(409,"Không thể chuyển sản phẩm sang trạng thái yêu cầu")
                    review_status='pending' if target=='pending_review' else product['status']; now=int(time.time())
                    db.execute("UPDATE products SET status=?,lifecycle_status=?,badge=?,updated_at=? WHERE id=? AND owner_id=?",(review_status,target,'Chờ duyệt' if target=='pending_review' else target,now,pid,actor['id']))
                    db.execute("INSERT INTO product_history(product_id,actor_id,action,snapshot_json,created_at) VALUES(?,?,?,?,?)",(pid,actor['id'],'lifecycle.'+action,json.dumps({"from":product['lifecycle_status'],"to":target},ensure_ascii=False),now))
                return self.send_json(200,{"ok":True,"lifecycle_status":target})
            if method=="POST" and path=="/api/products":
                user=self.require_role('seller'); name=str(data.get('name','')).strip(); category=str(data.get('category','')); price=data.get('price'); condition=str(data.get('condition','')); description=str(data.get('description','')); stock=data.get('stock',1); weight_kg=data.get('weight_kg',1)
                if not name or len(name)>100 or category not in ('Nội thất','Thời trang','Điện tử','Đồ gia dụng','Tái chế') or not isinstance(price,int) or price<1000 or price>1_000_000_000 or len(description)>5000 or not isinstance(stock,int) or not 0<=stock<=10000 or not isinstance(weight_kg,(int,float)) or isinstance(weight_kg,bool) or not 0<weight_kg<=1000: raise APIError(400,"Thông tin sản phẩm hoặc khối lượng chưa hợp lệ")
                description=safe_product_text(data.get('description',''),5000,'Mô tả'); short=safe_product_text(data.get('short_description',description[:180]),180,'Mô tả ngắn'); name=safe_product_text(name,100,'Tên sản phẩm'); condition=safe_product_text(condition,100,'Tình trạng')
                raw_slug=safe_product_text(data.get('slug',''),120,'Slug'); slug=slugify(raw_slug or name)
                if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug): raise APIError(400,"Slug chỉ gồm chữ thường, số và dấu gạch ngang")
                specifications=data.get('specifications',{})
                if not isinstance(specifications,dict) or len(specifications)>30 or any(not isinstance(k,str) or not isinstance(v,(str,int,float,bool)) for k,v in specifications.items()): raise APIError(400,"Thông số cần là đối tượng JSON với tối đa 30 thuộc tính đơn giản")
                specifications_json=json.dumps(specifications,ensure_ascii=False)
                if len(specifications_json)>5000: raise APIError(400,"Thông số sản phẩm vượt quá 5.000 ký tự")
                shipping_policy=safe_product_text(data.get('shipping_policy',''),500,'Chính sách giao hàng'); return_policy=safe_product_text(data.get('return_policy',''),500,'Chính sách đổi trả')
                image_paths=data.get('image_paths',[])
                if not isinstance(image_paths,list) or len(image_paths)>5 or any(not isinstance(path,str) or not re.fullmatch(r'/assets/uploads/[a-f0-9]{32}\.(?:png|jpg|webp)',path) or not (UPLOAD_DIR/path.rsplit('/',1)[-1]).is_file() for path in image_paths): raise APIError(400,"Ảnh sản phẩm không hợp lệ; tải tối đa 5 ảnh qua chức năng upload")
                appearance=data.get('appearance_score',80); functionality=data.get('functionality','working'); wear=data.get('wear_level','medium'); accessories=data.get('accessories','complete'); years=data.get('usage_years',0); recycled_pct=data.get('recycled_material_pct')
                rentable=data.get('rentable',False); rental_price=data.get('rental_price_day',0); rental_stock=data.get('rental_stock',1)
                if not isinstance(appearance,int) or not 0<=appearance<=100 or functionality not in ('working','partial','not_working') or wear not in ('low','medium','high') or accessories not in ('complete','partial','none') or not isinstance(years,int) or not 0<=years<=50 or (recycled_pct is not None and (not isinstance(recycled_pct,int) or not 0<=recycled_pct<=100)): raise APIError(400,"Thông tin đánh giá tình trạng không hợp lệ")
                if recycled_pct is not None and category!='Tái chế': raise APIError(400,"Tỷ lệ vật liệu tái chế chỉ áp dụng cho sản phẩm thuộc danh mục Tái chế")
                if not isinstance(rentable,bool) or not isinstance(rental_price,int) or not isinstance(rental_stock,int) or rental_stock<1 or (rentable and not 1000<=rental_price<=100_000_000): raise APIError(400,"Thông tin giá và số lượng cho thuê không hợp lệ")
                score=round(appearance*.35+{'working':100,'partial':55,'not_working':0}[functionality]*.30+{'low':100,'medium':70,'high':35}[wear]*.20+{'complete':100,'partial':60,'none':20}[accessories]*.10+max(0,100-years*5)*.05)
                emoji={'Nội thất':'🪑','Thời trang':'🧥','Điện tử':'📷','Đồ gia dụng':'🏺','Tái chế':'♻️'}[category]; pid='u'+secrets.token_hex(8)
                with connect() as db:
                    profile=db.execute("SELECT business_type,display_name FROM seller_profiles WHERE user_id=? AND status='approved'",(user['id'],)).fetchone()
                    if not profile: raise APIError(403,"Hồ sơ người bán chưa được duyệt")
                    for image in image_paths:
                        asset=db.execute("SELECT owner_id,product_id FROM upload_assets WHERE path=?",(image,)).fetchone()
                        if not asset or asset['owner_id']!=user['id'] or asset['product_id'] is not None: raise APIError(403,"Ảnh phải do chính tài khoản này vừa tải lên")
                    if db.execute("SELECT 1 FROM products WHERE slug=?",(slug,)).fetchone(): raise APIError(409,"Slug sản phẩm đã được sử dụng")
                    now=int(time.time()); draft=data.get('submit_for_review',True) is False; lifecycle='draft' if draft else 'pending_review'
                    db.execute("INSERT INTO products(id,name,category,condition,seller,price,emoji,bg,badge,co2,rentable,description,owner_id,status,created_at,stock,rental_price_day,rental_stock,slug,short_description,specifications_json,seller_type,shipping_policy,return_policy,lifecycle_status,updated_at,weight_grams) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,name,category,condition.upper(),profile['display_name'],price,emoji,'#e8ecdf','Bản nháp' if draft else 'Chờ duyệt',0,1 if rentable else 0,description,user['id'],now,stock,rental_price if rentable else 0,rental_stock,slug,short,specifications_json,profile['business_type'],shipping_policy,return_policy,lifecycle,now,round(weight_kg*1000)))
                    db.execute("UPDATE products SET item_type=?,category_id=(SELECT id FROM categories WHERE slug=CASE category WHEN 'Điện tử' THEN 'dien-tu' WHEN 'Thời trang' THEN 'thoi-trang' WHEN 'Đồ gia dụng' THEN 'do-gia-dung' WHEN 'Nội thất' THEN 'do-gia-dung' ELSE 'san-pham-tai-che' END) WHERE id=?",('recycled' if category=='Tái chế' else 'used',pid))
                    db.execute("INSERT INTO product_condition_assessments(product_id,appearance_score,functionality,wear_level,accessories,usage_years,score,recycled_material_pct,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(pid,appearance,functionality,wear,accessories,years,score,recycled_pct,now))
                    db.executemany("INSERT INTO product_images(product_id,image_path,alt_text,sort_order,created_at) VALUES(?,?,?,?,?)",[(pid,p,name,i,now) for i,p in enumerate(image_paths)])
                    db.executemany("UPDATE upload_assets SET product_id=? WHERE path=? AND owner_id=?",( (pid,p,user['id']) for p in image_paths))
                    snapshot={"name":name,"slug":slug,"category":category,"price":price,"stock":stock,"description":description,"lifecycle_status":lifecycle}
                    db.execute("INSERT INTO product_history(product_id,actor_id,action,snapshot_json,created_at) VALUES(?,?, 'created',?,?)",(pid,user['id'],json.dumps(snapshot,ensure_ascii=False),now))
                return self.send_json(201,{"id":pid,"status":"pending" if not draft else "draft","lifecycle_status":lifecycle,"condition_score":score})
            if method=="POST" and path=="/api/seller/apply":
                user=self.require_role('customer','seller'); kind=data.get('business_type'); display=str(data.get('display_name','')).strip(); desc=str(data.get('description','')).strip()
                if kind not in ('c2c','b2c') or not display or len(display)>100 or len(desc)>500: raise APIError(400,"Thông tin hồ sơ người bán chưa hợp lệ")
                with connect() as db:
                    old=db.execute("SELECT status FROM seller_profiles WHERE user_id=?",(user['id'],)).fetchone()
                    if old and old['status']=='approved': raise APIError(409,"Hồ sơ người bán đã được duyệt")
                    db.execute("INSERT INTO seller_profiles(user_id,business_type,display_name,description,status,created_at) VALUES(?,?,?,?, 'pending',?) ON CONFLICT(user_id) DO UPDATE SET business_type=excluded.business_type,display_name=excluded.display_name,description=excluded.description,status='pending'",(user['id'],kind,display,desc,int(time.time())))
                return self.send_json(201,{"status":"pending"})
            if method=="POST" and path=="/api/addresses":
                user=self.require_role('customer','seller'); recipient=str(data.get('recipient','')).strip(); phone=str(data.get('phone','')).strip(); address=str(data.get('address','')).strip()
                if not recipient or len(recipient)>100 or len(phone)<8 or len(phone)>20 or len(address)<5 or len(address)>300: raise APIError(400,"Thông tin địa chỉ chưa hợp lệ")
                with connect() as db:
                    if data.get('is_default'): db.execute("UPDATE addresses SET is_default=0 WHERE user_id=?",(user['id'],))
                    cur=db.execute("INSERT INTO addresses(user_id,recipient,phone,address,is_default,created_at) VALUES(?,?,?,?,?,?)",(user['id'],recipient,phone,address,int(bool(data.get('is_default'))),int(time.time())))
                return self.send_json(201,{"id":cur.lastrowid})
            if method=="POST" and path=="/api/favorites":
                user=self.require_role('customer','seller'); pid=str(data.get('product_id',''))
                with connect() as db:
                    if not db.execute("SELECT 1 FROM products WHERE id=? AND status='approved' AND lifecycle_status='active'",(pid,)).fetchone(): raise APIError(404,"Sản phẩm không còn khả dụng")
                    db.execute("INSERT OR IGNORE INTO favorites(user_id,product_id,created_at) VALUES(?,?,?)",(user['id'],pid,int(time.time())))
                return self.send_json(201,{"ok":True})
            if method=="POST" and path=="/api/reviews":
                user=self.require_role('customer','seller'); oid=str(data.get('order_id','')); pid=str(data.get('product_id','')); rating=data.get('rating'); body=' '.join(str(data.get('body','')).split())
                if not isinstance(rating,int) or not 1<=rating<=5 or not body or len(body)>1000 or len(body)<3: raise APIError(400,"Đánh giá cần có 1–5 sao và nội dung từ 3 đến 1.000 ký tự")
                body=re.sub(r'<[^>]*>','',body); body=''.join(ch for ch in body if ch in '\n\t' or ord(ch)>=32).strip()
                if not 3<=len(body)<=1000: raise APIError(400,"Nội dung đánh giá không hợp lệ sau khi làm sạch")
                with connect() as db:
                    eligible=db.execute("SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id WHERE o.id=? AND o.user_id=? AND o.kind='purchase' AND o.status='Hoàn tất' AND oi.product_id=?",(oid,user['id'],pid)).fetchone()
                    if not eligible: raise APIError(403,"Chỉ được đánh giá sản phẩm đã mua trong đơn hoàn tất")
                    try: cur=db.execute("INSERT INTO reviews(order_id,product_id,user_id,rating,body,status,created_at) VALUES(?,?,?,?,?,'pending',?)",(oid,pid,user['id'],rating,body,int(time.time())))
                    except sqlite3.IntegrityError: raise APIError(409,"Bạn đã gửi đánh giá cho sản phẩm này trong đơn")
                return self.send_json(201,{"id":cur.lastrowid,"status":"pending"})
            if method=="POST" and path=="/api/admin/vouchers":
                actor=self.require_role('admin'); code=str(data.get('code','')).strip().upper(); kind=data.get('discount_type'); value=data.get('value'); minimum=data.get('min_order',0); maximum=data.get('max_discount'); starts=data.get('starts_at'); ends=data.get('ends_at'); limit=data.get('usage_limit'); per_user=data.get('per_user_limit',1)
                if not code or len(code)>32 or not code.replace('-','').isalnum() or kind not in ('percent','fixed') or not isinstance(value,int) or value<1 or (kind=='percent' and value>100) or not isinstance(minimum,int) or minimum<0 or (maximum is not None and (not isinstance(maximum,int) or maximum<1)) or not isinstance(starts,int) or not isinstance(ends,int) or starts>=ends or (limit is not None and (not isinstance(limit,int) or limit<1)) or not isinstance(per_user,int) or per_user<1: raise APIError(400,"Thông tin voucher không hợp lệ")
                with connect() as db:
                    try: cur=db.execute("INSERT INTO vouchers(code,discount_type,value,min_order,max_discount,starts_at,ends_at,usage_limit,per_user_limit,is_active,created_at) VALUES(?,?,?,?,?,?,?,?,?,1,?)",(code,kind,value,minimum,maximum,starts,ends,limit,per_user,int(time.time())))
                    except sqlite3.IntegrityError: raise APIError(409,"Mã voucher đã tồn tại")
                    self.audit(db,actor,'voucher.create','voucher',cur.lastrowid,code)
                return self.send_json(201,{"id":cur.lastrowid,"code":code})
            if method=="POST" and path=="/api/vouchers/validate":
                user=self.require_role('customer','seller'); code=str(data.get('code','')).strip(); items=data.get('items')
                if not isinstance(items,list) or not items: raise APIError(400,"Giỏ hàng trống hoặc không hợp lệ")
                subtotal=0; total_weight_grams=0
                with connect() as db:
                    for item in items:
                        if not isinstance(item,dict) or not isinstance(item.get('qty'),int) or item['qty']<1: raise APIError(400,"Số lượng sản phẩm không hợp lệ")
                        p=db.execute("SELECT price,stock,weight_grams FROM products WHERE id=? AND status='approved' AND lifecycle_status='active'",(str(item.get('id','')),)).fetchone()
                        if not p or p['stock']<item['qty']: raise APIError(400,"Sản phẩm không khả dụng hoặc không đủ tồn kho")
                        subtotal+=p['price']*item['qty']; total_weight_grams+=p['weight_grams']*item['qty']
                    voucher,discount=self.voucher_discount(db,user,code,subtotal)
                shipping_fee=0 if total_weight_grams>=SHIPPING_FREE_THRESHOLD_GRAMS else SHIPPING_UNDER_THRESHOLD_FEE
                return self.send_json(200,{"code":voucher['code'],"subtotal":subtotal,"discount":discount,"shipping_fee":shipping_fee,"total_weight_grams":total_weight_grams,"total_weight_kg":round(total_weight_grams/1000,3),"total":subtotal-discount+shipping_fee})
            if method=="POST" and path=="/api/admin/categories":
                actor=self.require_role('admin'); name=str(data.get('name','')).strip(); slug=str(data.get('slug','')).strip().lower(); parent=data.get('parent_id'); order=data.get('sort_order',0)
                if not name or len(name)>80 or not slug or len(slug)>100 or not all(c.isalnum() or c=='-' for c in slug) or not isinstance(order,int): raise APIError(400,"Tên, slug hoặc thứ tự danh mục không hợp lệ")
                with connect() as db:
                    if parent is not None and not db.execute("SELECT 1 FROM categories WHERE id=? AND is_active=1",(parent,)).fetchone(): raise APIError(400,"Danh mục cha không tồn tại hoặc đang ẩn")
                    try: cur=db.execute("INSERT INTO categories(name,slug,parent_id,sort_order,created_at) VALUES(?,?,?,?,?)",(name,slug,parent,order,int(time.time())))
                    except sqlite3.IntegrityError: raise APIError(409,"Slug danh mục đã tồn tại hoặc quan hệ không hợp lệ")
                    self.audit(db,actor,'category.create','category',cur.lastrowid)
                return self.send_json(201,{"id":cur.lastrowid})
            if method=="POST" and path=="/api/admin/impact-factors":
                actor=self.current_user(True,True); item_type=data.get('item_type'); value=data.get('factor_value'); unit=str(data.get('unit','')).strip(); scope=str(data.get('scope','')).strip(); source=str(data.get('source_name','')).strip(); url=str(data.get('source_url','')).strip()
                if item_type not in ('used','recycled') or not isinstance(value,(int,float)) or value<0 or not unit or len(unit)>60 or not scope or len(scope)>300 or not source or len(source)>200 or not re.match(r'^https://[^\s]+$',url) or len(url)>500: raise APIError(400,"Cần hệ số hợp lệ, đơn vị, phạm vi và URL nguồn HTTPS")
                with connect() as db:
                    version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM impact_factors WHERE item_type=?",(item_type,)).fetchone()[0]
                    db.execute("UPDATE impact_factors SET active=0 WHERE item_type=? AND active=1",(item_type,))
                    cur=db.execute("INSERT INTO impact_factors(item_type,factor_value,unit,scope,source_name,source_url,version,active,created_at) VALUES(?,?,?,?,?,?,?,1,?)",(item_type,float(value),unit,scope,source,url,version,int(time.time())))
                    self.audit(db,actor,'impact_factor.create','impact_factor',cur.lastrowid,f'{item_type} v{version} · {source} · {url}')
                return self.send_json(201,{"id":cur.lastrowid,"version":version})
            if method=="POST" and path=="/api/orders": return self.create_order(data)
            if method=="POST" and path=="/api/support-requests":
                user=self.current_user(True); category=data.get('category'); subject=' '.join(str(data.get('subject','')).split()); details=' '.join(str(data.get('details','')).split()); order_id=data.get('order_id') or None
                if category not in ('complaint','order','product','payment','other') or not 4<=len(subject)<=120 or not 10<=len(details)<=2000: raise APIError(400,"Loại, tiêu đề hoặc nội dung yêu cầu chưa hợp lệ")
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    active=db.execute("SELECT COUNT(*) FROM support_requests WHERE user_id=? AND status IN ('pending','processing')",(user['id'],)).fetchone()[0]
                    if active>=5: raise APIError(429,"Bạn đang có 5 yêu cầu chưa xử lý; vui lòng chờ kết quả")
                    if order_id and not db.execute("SELECT 1 FROM orders WHERE id=? AND user_id=?",(order_id,user['id'])).fetchone(): raise APIError(404,"Không tìm thấy đơn hàng của bạn")
                    now=int(time.time()); cur=db.execute("INSERT INTO support_requests(user_id,order_id,category,subject,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(user['id'],order_id,category,subject,details,now,now)); self.audit(db,user,'support_request.create','support_request',cur.lastrowid,category)
                return self.send_json(201,{"id":cur.lastrowid,"status":"pending"})
            if method=="POST" and path=="/api/privacy-requests":
                user=self.current_user(True); kind=data.get('request_type'); details=' '.join(str(data.get('details','')).split())
                if kind not in ('access','correction','deletion','objection','other') or len(details)<3 or len(details)>1200: raise APIError(400,"Loại yêu cầu hoặc nội dung chưa hợp lệ")
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE'); active=db.execute("SELECT COUNT(*) FROM privacy_requests WHERE user_id=? AND status IN ('pending','processing')",(user['id'],)).fetchone()[0]
                    if active>=3: raise APIError(429,"Bạn đang có 3 yêu cầu chưa xử lý; vui lòng chờ kết quả trước khi gửi thêm")
                    now=int(time.time()); cur=db.execute("INSERT INTO privacy_requests(user_id,request_type,details,created_at,updated_at) VALUES(?,?,?,?,?)",(user['id'],kind,details,now,now)); self.audit(db,user,'privacy_request.create','privacy_request',cur.lastrowid,kind)
                return self.send_json(201,{"id":cur.lastrowid,"status":"pending","message":"Đã ghi nhận yêu cầu; nhóm vận hành cần cấu hình kênh liên hệ và xử lý theo quy định hiện hành."})
            if method=="POST" and path=="/api/points/redeem":
                user=self.current_user(True); points=data.get('points')
                if not isinstance(points,int) or points<100 or points%100: raise APIError(400,"Đổi tối thiểu 100 điểm và theo bội số 100")
                with connect() as db:
                    db.execute("BEGIN IMMEDIATE"); balance=db.execute("SELECT COALESCE(SUM(points),0) FROM points_ledger WHERE user_id=?",(user['id'],)).fetchone()[0]
                    if points>balance: raise APIError(409,"Số dư điểm không đủ")
                    code='XANH-'+secrets.token_hex(4).upper(); voucher_value=(points//100)*10000; now=int(time.time())
                    db.execute("INSERT INTO points_ledger(user_id,points,event_type,reference_type,reference_id,note,created_at) VALUES(?,?,'redeem','voucher',?,?,?)",(user['id'],-points,code,f'Đổi thành voucher {voucher_value}đ',now))
                    db.execute("INSERT INTO vouchers(code,discount_type,value,min_order,max_discount,starts_at,ends_at,usage_limit,per_user_limit,is_active,created_at) VALUES(?,'fixed',?,0,?, ?,?,1,1,1,?)",(code,voucher_value,voucher_value,now,now+90*86400,now))
                    self.audit(db,user,'points.redeem','voucher',code,f'points={points}; value={voucher_value}')
                return self.send_json(201,{"code":code,"points_spent":points,"value":voucher_value,"balance":balance-points})
            if method=="POST" and path.startswith('/api/orders/') and path.endswith('/cancel'):
                user=self.require_role('customer','seller'); oid=path.split('/')[-2]
                with connect() as db:
                    row=db.execute("SELECT status,payment_status,payment FROM orders WHERE id=? AND user_id=?",(oid,user['id'])).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy đơn hàng")
                    if row['status'] not in ('Đang xử lý','Chờ thanh toán'): raise APIError(409,"Đơn hàng không còn ở trạng thái được phép hủy")
                    if row['payment_status']=='paid': raise APIError(409,"Đơn đã thanh toán; hãy gửi yêu cầu hỗ trợ/hoàn tiền thay vì hủy")
                    for item in db.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?",(oid,)).fetchall(): db.execute("UPDATE products SET stock=stock+?,lifecycle_status=CASE WHEN lifecycle_status='out_of_stock' AND status='approved' THEN 'active' ELSE lifecycle_status END,updated_at=? WHERE id=?",(item['quantity'],int(time.time()),item['product_id']))
                    db.execute("UPDATE orders SET status='Đã hủy' WHERE id=?",(oid,))
                    if row['payment'] in ('VNPAY','VNPAY_QR'):
                        now=int(time.time())
                        if row['payment']=='VNPAY': db.execute("UPDATE payment_transactions SET status='cancelled',updated_at=? WHERE order_id=? AND status='pending'",(now,oid))
                        db.execute("UPDATE orders SET payment_status='cancelled' WHERE id=?",(oid,))
                        source='customer_vnpay' if row['payment']=='VNPAY' else 'customer_qr_transfer'
                        db.execute("INSERT INTO payment_status_history(order_id,payment_status,actor_id,source,note,created_at) VALUES(?,'cancelled',?,?,?,?)",(oid,user['id'],source,'Đơn thanh toán bị hủy; đã giải phóng tồn kho',now))
                    db.execute("UPDATE rental_reservations SET status='cancelled' WHERE order_id=? AND status='requested'",(oid,))
                    db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)",(oid,'Đã hủy',user['id'],'Khách hàng hủy đơn',int(time.time())))
                return self.send_json(200,{"ok":True,"status":"Đã hủy"})
            if method=="POST" and path=="/api/rentals": return self.create_rental(data)
            if method=="POST" and path=="/api/subscriptions":
                user=self.current_user(True); plans={'ReBox Mini':199000,'ReBox Chọn':349000,'ReBox Tặng':499000}; plan=str(data.get('plan','')).split(' — ')[0]
                if plan not in plans: raise APIError(400,"Gói không hợp lệ")
                now=date.today(); due=now+timedelta(days=30)
                with connect() as db: cur=db.execute("INSERT INTO subscriptions(user_id,plan,price,status,created_at,cadence,starts_at,next_due_at) VALUES(?,?,?,'active',?,'monthly',?,?)",(user['id'],plan,plans[plan],int(time.time()),now.isoformat(),due.isoformat()))
                return self.send_json(201,{"id":cur.lastrowid,"plan":plan,"price":plans[plan],"status":"active","cadence":"monthly","starts_at":now.isoformat(),"next_due_at":due.isoformat(),"mode":"manual demo; không tự thu tiền"})
            if method=="POST" and path.startswith('/api/subscriptions/') and path.endswith('/cancel'):
                user=self.current_user(True); sid=path.split('/')[-2]
                with connect() as db:
                    cur=db.execute("UPDATE subscriptions SET status='cancelled',cancelled_at=? WHERE id=? AND user_id=? AND status='active'",(int(time.time()),sid,user['id']))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy gói đang hoạt động của bạn")
                return self.send_json(200,{"ok":True,"status":"cancelled"})
            raise APIError(404,"Không tìm thấy API")
        except APIError as e:self.send_json(e.status,{"error":e.message})
        except Exception as e: print("API error:",repr(e)); self.send_json(500,{"error":"Lỗi máy chủ"})

    def do_DELETE(self):
        try:
            self.check_origin(require_origin=bool(self.cookies().get(COOKIE))); path=urlparse(self.path).path; user=self.require_role('customer','seller')
            if path.startswith('/api/favorites/'):
                pid=path.rsplit('/',1)[-1]
                with connect() as db: db.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?",(user['id'],pid))
                return self.send_json(200,{"ok":True})
            if path.startswith('/api/addresses/'):
                aid=path.rsplit('/',1)[-1]
                with connect() as db: cur=db.execute("DELETE FROM addresses WHERE id=? AND user_id=?",(aid,user['id']))
                if not cur.rowcount: raise APIError(404,"Không tìm thấy địa chỉ")
                return self.send_json(200,{"ok":True})
            raise APIError(404,"Không tìm thấy API")
        except APIError as e:self.send_json(e.status,{"error":e.message})
        except Exception as e: print("API error:",repr(e)); self.send_json(500,{"error":"Lỗi máy chủ"})

    def create_order(self,data):
        user=self.current_user(True); items=data.get('items'); payment=data.get('payment'); address=str(data.get('address','')).strip()
        if not isinstance(items,list) or not items or len(items)>50 or len(address)<5 or len(address)>300 or payment not in ('COD','VNPAY','VNPAY_QR'): raise APIError(400,"Thông tin đặt hàng không hợp lệ")
        if data.get('terms_accepted') is not True or data.get('terms_version')!=POLICY_VERSION: raise APIError(400,"Vui lòng rà soát và xác nhận Điều kiện giao dịch phiên bản hiện hành")
        if payment=='VNPAY' and not all(vnpay_settings()[k] for k in ('tmn_code','hash_secret','return_url','ipn_url')): raise APIError(503,"VNPay sandbox chưa được cấu hình credentials và URL callback; không tạo đơn hàng")
        idem=str(data.get('idempotency_key') or self.headers.get('Idempotency-Key','')).strip()
        if not idem or len(idem)>100 or not re.fullmatch(r'[A-Za-z0-9._:-]{16,100}',idem): raise APIError(400,"Thiếu khóa idempotency hợp lệ để chống tạo đơn trùng")
        payload_hash=hashlib.sha256(json.dumps({"items":items,"payment":payment,"address":address,"voucher_code":str(data.get('voucher_code','')).strip(),"terms_version":POLICY_VERSION},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        order_id='RL'+secrets.token_hex(4).upper(); subtotal=0; parsed=[]; quantities={}; payment_url=None; reference=None; total_weight_grams=0; shipping_fee=0
        for item in items:
            if not isinstance(item,dict): raise APIError(400,"Dòng sản phẩm không hợp lệ")
            pid=str(item.get('id','')); qty=item.get('qty')
            if not isinstance(qty,int) or qty<1 or qty>20: raise APIError(400,"Số lượng không hợp lệ")
            quantities[pid]=quantities.get(pid,0)+qty
            if quantities[pid]>20: raise APIError(400,"Số lượng mỗi sản phẩm tối đa là 20")
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior=db.execute("SELECT c.payload_hash,c.order_id,o.total,o.payment,o.status,o.payment_status,o.provider_reference,o.shipping_fee,o.total_weight_grams FROM checkout_idempotency c JOIN orders o ON o.id=c.order_id WHERE c.user_id=? AND c.idempotency_key=?",(user['id'],idem)).fetchone()
            if prior:
                if prior['payload_hash']!=payload_hash: raise APIError(409,"Khóa đặt hàng đã được dùng cho nội dung khác")
                if prior['payment']=='VNPAY':
                    tx=db.execute("SELECT txn_ref FROM payment_transactions WHERE order_id=? AND status='pending'",(prior['order_id'],)).fetchone()
                    if tx: payment_url=build_vnpay_url(tx['txn_ref'],prior['total'],self.client_address[0])[0]
                return self.send_json(200,{"id":prior['order_id'],"total":prior['total'],"payment":prior['payment'],"status":prior['status'],"payment_status":prior['payment_status'],"provider_reference":prior['provider_reference'],"payment_url":payment_url,"qr_image":"/assets/vnpay-personal-qr.jpg" if prior['payment']=='VNPAY_QR' else None,"shipping_fee":prior['shipping_fee'],"total_weight_grams":prior['total_weight_grams'],"accepted_terms_version":POLICY_VERSION,"idempotent_replay":True})
            for pid,qty in quantities.items():
                p=db.execute("SELECT id,name,price,stock,weight_grams FROM products WHERE id=? AND status='approved' AND lifecycle_status='active'",(pid,)).fetchone()
                if not p or p['stock']<qty: raise APIError(400,"Sản phẩm không khả dụng hoặc không đủ tồn kho")
                subtotal+=p['price']*qty; total_weight_grams+=(p['weight_grams'] or 1000)*qty; parsed.append((p,qty))
            if subtotal>2_000_000_000: raise APIError(400,"Giá trị đơn vượt giới hạn")
            shipping_fee=0 if total_weight_grams>=SHIPPING_FREE_THRESHOLD_GRAMS else SHIPPING_UNDER_THRESHOLD_FEE
            voucher,discount=self.voucher_discount(db,user,str(data.get('voucher_code','')),subtotal) if data.get('voucher_code') else (None,0); total=subtotal-discount+shipping_fee
            expected=data.get('expected_total')
            if expected is not None and (not isinstance(expected,int) or expected!=subtotal): raise APIError(409,"Giá hoặc số lượng sản phẩm đã thay đổi. Hãy kiểm tra lại giỏ hàng")
            now=int(time.time()); expires=None
            if payment=='VNPAY':
                payment_url,expires=build_vnpay_url(order_id,total,self.client_address[0])
                reference=order_id
            db.execute("INSERT INTO orders(id,user_id,total,payment,status,kind,address,created_at,provider_reference,payment_status,payment_expires_at,accepted_terms_version,terms_accepted_at,shipping_fee,total_weight_grams) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(order_id,user['id'],total,payment,'Đang xử lý','purchase',address,now,reference,'pending' if payment=='VNPAY' else 'unpaid',expires,POLICY_VERSION,now,shipping_fee,total_weight_grams))
            db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)",(order_id,'Đang xử lý',user['id'],'Đơn hàng được tạo',int(time.time())))
            db.execute("INSERT INTO payment_status_history(order_id,payment_status,actor_id,source,note,created_at) VALUES(?,?,?,?,?,?)",(order_id,'pending' if payment=='VNPAY' else 'unpaid',user['id'],'checkout','Khởi tạo phương thức '+payment,now))
            db.executemany("INSERT INTO order_items(order_id,product_id,name,price,quantity) VALUES(?,?,?,?,?)",[(order_id,p['id'],p['name'],p['price'],qty) for p,qty in parsed])
            for p,qty in parsed: db.execute("UPDATE products SET stock=stock-?,lifecycle_status=CASE WHEN stock-?<=0 THEN 'out_of_stock' ELSE lifecycle_status END,updated_at=? WHERE id=?",(qty,qty,int(time.time()),p['id']))
            if voucher: db.execute("INSERT INTO voucher_redemptions(voucher_id,user_id,order_id,discount,created_at) VALUES(?,?,?,?,?)",(voucher['id'],user['id'],order_id,discount,int(time.time())))
            if payment=='VNPAY': db.execute("INSERT INTO payment_transactions(order_id,provider,txn_ref,amount,status,created_at,updated_at) VALUES(?,'VNPAY',?,?,'pending',?,?)",(order_id,order_id,total,now,now))
            db.execute("INSERT INTO checkout_idempotency(user_id,idempotency_key,payload_hash,order_id,created_at) VALUES(?,?,?,?,?)",(user['id'],idem,payload_hash,order_id,now))
            self.audit(db,user,'order.create','order',order_id,f'{payment} · subtotal={subtotal} · shipping={shipping_fee} · total={total}')
        subject,body=email_templates.order_confirmation(order_id,total,payment); notice=self.queue_email(user['id'],subject,body)
        return self.send_json(201,{"id":order_id,"subtotal":subtotal,"discount":discount,"shipping_fee":shipping_fee,"total_weight_grams":total_weight_grams,"total_weight_kg":round(total_weight_grams/1000,3),"total":total,"voucher_code":voucher['code'] if voucher else None,"payment":payment,"status":"Đang xử lý","payment_status":"pending" if payment=='VNPAY' else 'unpaid',"provider_reference":reference,"payment_url":payment_url,"qr_image":"/assets/vnpay-personal-qr.jpg" if payment=='VNPAY_QR' else None,"points_pending":max(0,subtotal-discount)//10000,"email_status":notice or "unavailable","accepted_terms_version":POLICY_VERSION,"terms_accepted_at":now})

    def create_rental(self,data):
        user=self.current_user(True); pid=str(data.get('id','')); days=data.get('days'); address=str(data.get('address','')).strip(); start=str(data.get('start',''))
        if data.get('terms_accepted') is not True or data.get('terms_version')!=POLICY_VERSION: raise APIError(400,"Vui lòng rà soát và xác nhận Điều kiện thuê phiên bản hiện hành")
        try: rental_date=date.fromisoformat(start)
        except ValueError: raise APIError(400,"Ngày thuê không hợp lệ")
        if not isinstance(days,int) or not 1<=days<=30 or len(address)<5 or len(address)>300 or rental_date<date.today(): raise APIError(400,"Thông tin thuê không hợp lệ")
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p=db.execute("SELECT id,name,owner_id,rental_price_day FROM products WHERE id=? AND rentable=1 AND status='approved' AND lifecycle_status='active'",(pid,)).fetchone()
            if not p: raise APIError(404,"Sản phẩm hiện không hỗ trợ thuê")
            if p['owner_id']==user['id']: raise APIError(403,"Bạn không thể gửi yêu cầu thuê sản phẩm do chính mình đăng bán")
            end_date=rental_date+timedelta(days=days-1); active=db.execute("SELECT COALESCE(SUM(quantity),0) FROM rental_reservations WHERE product_id=? AND status IN ('requested','confirmed','handed_out') AND start_date<=? AND end_date>=?",(pid,end_date.isoformat(),rental_date.isoformat())).fetchone()[0]
            rental_stock=db.execute("SELECT rental_stock FROM products WHERE id=?",(pid,)).fetchone()[0]
            if active>=max(1,rental_stock): raise APIError(409,"Sản phẩm đã được đặt thuê trong một phần thời gian này")
            oid='RT'+secrets.token_hex(4).upper(); day_price=p['rental_price_day'] or 49000
            if not isinstance(day_price,int) or not 1000<=day_price<=100_000_000: raise APIError(409,"Sản phẩm chưa có giá thuê hợp lệ; vui lòng liên hệ người bán")
            total=days*day_price
            if total>2_000_000_000: raise APIError(400,"Tổng tiền thuê vượt giới hạn")
            now=int(time.time()); db.execute("INSERT INTO orders(id,user_id,total,payment,status,kind,address,created_at,accepted_terms_version,terms_accepted_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(oid,user['id'],total,'Yêu cầu thuê','Đang xử lý','rental',f'{address} · thuê {days} ngày từ {start}',now,POLICY_VERSION,now))
            db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)",(oid,'Đang xử lý',user['id'],'Yêu cầu thuê được tạo',int(time.time())))
            cur=db.execute("INSERT INTO order_items(order_id,product_id,name,price,quantity,rental_days) VALUES(?,?,?,?,1,?)",(oid,p['id'],p['name'],day_price,days))
            db.execute("INSERT INTO rental_reservations(order_id,product_id,user_id,start_date,end_date,quantity,status,deposit_amount,created_at) VALUES(?,?,?,?,?,1,'requested',0,?)",(oid,pid,user['id'],rental_date.isoformat(),end_date.isoformat(),int(time.time())))
        return self.send_json(201,{"id":oid,"unit_price":day_price,"days":days,"total":total,"status":"Đang xử lý","start_date":rental_date.isoformat(),"end_date":end_date.isoformat(),"deposit_amount":0,"deposit_note":"Yêu cầu đang chờ người bán xác nhận; chưa thu tiền hoặc tiền ký quỹ trực tuyến"})

    def do_PATCH(self):
        try:
            self.check_origin(require_origin=bool(self.cookies().get(COOKIE))); data=self.read_json(); path=urlparse(self.path).path
            if path.startswith('/api/admin/reviews/'):
                actor=self.current_user(True,True); rid=path.rsplit('/',1)[-1]; status=data.get('status')
                if status not in ('approved','rejected'): raise APIError(400,"Trạng thái đánh giá không hợp lệ")
                with connect() as db:
                    cur=db.execute("UPDATE reviews SET status=? WHERE id=?",(status,rid))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy đánh giá")
                    self.audit(db,actor,'review.'+status,'review',rid)
                return self.send_json(200,{"ok":True,"status":status})
            if path.startswith('/api/admin/support-requests/'):
                actor=self.current_user(True,True); rid=path.rsplit('/',1)[-1]; status=data.get('status'); note=' '.join(str(data.get('admin_note','')).split())
                if status not in ('processing','resolved','rejected') or len(note)>1000: raise APIError(400,"Trạng thái hoặc ghi chú xử lý không hợp lệ")
                with connect() as db:
                    cur=db.execute("UPDATE support_requests SET status=?,admin_note=?,updated_at=? WHERE id=?",(status,note,int(time.time()),rid))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy yêu cầu hỗ trợ")
                    self.audit(db,actor,'support_request.'+status,'support_request',rid,note)
                return self.send_json(200,{"ok":True,"status":status})
            if path.startswith('/api/admin/privacy-requests/'):
                actor=self.current_user(True,True); rid=path.rsplit('/',1)[-1]; status=data.get('status'); note=' '.join(str(data.get('resolution_note','')).split())
                if status not in ('processing','completed','rejected') or len(note)>1000: raise APIError(400,"Trạng thái hoặc nội dung xử lý không hợp lệ")
                with connect() as db:
                    cur=db.execute("UPDATE privacy_requests SET status=?,resolution_note=?,updated_at=? WHERE id=?",(status,note,int(time.time()),rid))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy yêu cầu dữ liệu cá nhân")
                    self.audit(db,actor,'privacy_request.'+status,'privacy_request',rid,note)
                return self.send_json(200,{"ok":True,"status":status})
            if path=="/api/admin/impact-factors":
                actor=self.current_user(True,True); item_type=data.get('item_type'); value=data.get('factor_value'); unit=str(data.get('unit','')).strip(); scope=str(data.get('scope','')).strip(); source=str(data.get('source_name','')).strip(); url=str(data.get('source_url','')).strip()
                if item_type not in ('used','recycled') or not isinstance(value,(int,float)) or value<0 or not unit or len(unit)>60 or not scope or len(scope)>300 or not source or len(source)>200 or not re.match(r'^https://[^\s]+$',url) or len(url)>500: raise APIError(400,"Cần hệ số hợp lệ, đơn vị, phạm vi và URL nguồn HTTPS")
                with connect() as db:
                    version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM impact_factors WHERE item_type=?",(item_type,)).fetchone()[0]
                    db.execute("UPDATE impact_factors SET active=0 WHERE item_type=? AND active=1",(item_type,))
                    cur=db.execute("INSERT INTO impact_factors(item_type,factor_value,unit,scope,source_name,source_url,version,active,created_at) VALUES(?,?,?,?,?,?,?,1,?)",(item_type,float(value),unit,scope,source,url,version,int(time.time())))
                    self.audit(db,actor,'impact_factor.create','impact_factor',cur.lastrowid,f'{item_type} v{version} · {source} · {url}')
                return self.send_json(201,{"id":cur.lastrowid,"version":version})
            if path.startswith('/api/seller/reviews/'):
                actor=self.require_role('seller'); rid=path.rsplit('/',1)[-1]; reply=' '.join(str(data.get('reply','')).split())
                if not reply or len(reply)>1000: raise APIError(400,"Phản hồi cần từ 1 đến 1.000 ký tự")
                with connect() as db:
                    cur=db.execute("UPDATE reviews SET seller_reply=?,replied_at=? WHERE id=? AND status='approved' AND product_id IN (SELECT id FROM products WHERE owner_id=?)",(reply,int(time.time()),rid,actor['id']))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy đánh giá đã duyệt thuộc sản phẩm của bạn")
                return self.send_json(200,{"ok":True})
            if path.startswith('/api/admin/vouchers/'):
                actor=self.current_user(True,True); vid=path.rsplit('/',1)[-1]; active=data.get('is_active')
                if active not in (0,1,False,True): raise APIError(400,"Trạng thái voucher không hợp lệ")
                with connect() as db:
                    cur=db.execute("UPDATE vouchers SET is_active=? WHERE id=?",(int(bool(active)),vid))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy voucher")
                    self.audit(db,actor,'voucher.toggle','voucher',vid,str(int(bool(active))))
                return self.send_json(200,{"ok":True,"is_active":bool(active)})
            if path.startswith('/api/products/'):
                user=self.current_user(True); pid=path.rsplit('/',1)[-1]
                with connect() as db:
                    row=db.execute("SELECT owner_id,status FROM products WHERE id=?",(pid,)).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy sản phẩm")
                    if user['role']!='admin' and (user['role']!='seller' or row['owner_id']!=user['id']): raise APIError(403,"Bạn chỉ được sửa sản phẩm của mình")
                    name=str(data.get('name','')).strip(); price=data.get('price'); stock=data.get('stock'); desc=str(data.get('description',''))
                    if not name or len(name)>100 or not isinstance(price,int) or price<1000 or not isinstance(stock,int) or not 0<=stock<=10000 or len(desc)>500: raise APIError(400,"Thông tin sản phẩm chưa hợp lệ")
                    db.execute("UPDATE products SET name=?,price=?,stock=?,description=?,status='pending',badge='Chờ duyệt' WHERE id=?",(name,price,stock,desc,pid))
                    self.audit(db,user,'product.edit','product',pid)
                return self.send_json(200,{"ok":True,"status":"pending"})
            if path.startswith('/api/admin/sellers/'):
                actor=self.current_user(True,True); uid=path.rsplit('/',1)[-1]; status=data.get('status')
                if status not in ('approved','rejected'): raise APIError(400,"Trạng thái hồ sơ không hợp lệ")
                with connect() as db:
                    row=db.execute("SELECT user_id FROM seller_profiles WHERE user_id=?",(uid,)).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy hồ sơ")
                    db.execute("UPDATE seller_profiles SET status=? WHERE user_id=?",(status,uid)); db.execute("UPDATE users SET role=? WHERE id=? AND role!='admin'",('seller' if status=='approved' else 'customer',uid)); self.audit(db,actor,'seller.'+status,'seller',uid)
                return self.send_json(200,{"ok":True,"status":status})
            if path.startswith('/api/admin/categories/'):
                actor=self.current_user(True,True); cid=path.rsplit('/',1)[-1]; name=str(data.get('name','')).strip(); slug=str(data.get('slug','')).strip().lower(); parent=data.get('parent_id'); active=data.get('is_active',1); order=data.get('sort_order',0)
                if not name or len(name)>80 or not slug or len(slug)>100 or not all(c.isalnum() or c=='-' for c in slug) or active not in (0,1,False,True) or not isinstance(order,int): raise APIError(400,"Thông tin danh mục không hợp lệ")
                with connect() as db:
                    if not db.execute("SELECT 1 FROM categories WHERE id=?",(cid,)).fetchone(): raise APIError(404,"Không tìm thấy danh mục")
                    if parent is not None:
                        if str(parent)==cid: raise APIError(400,"Danh mục không thể là cha của chính nó")
                        if not db.execute("SELECT 1 FROM categories WHERE id=? AND is_active=1",(parent,)).fetchone(): raise APIError(400,"Danh mục cha không tồn tại hoặc đang ẩn")
                        cycle=db.execute("WITH RECURSIVE descendants(id) AS (SELECT id FROM categories WHERE parent_id=? UNION ALL SELECT c.id FROM categories c JOIN descendants d ON c.parent_id=d.id) SELECT 1 FROM descendants WHERE id=?",(cid,parent)).fetchone()
                        if cycle: raise APIError(400,"Không thể tạo chu trình trong cây danh mục")
                    if not active and db.execute("SELECT 1 FROM categories WHERE parent_id=? AND is_active=1",(cid,)).fetchone(): raise APIError(409,"Hãy ẩn các danh mục con trước")
                    try: db.execute("UPDATE categories SET name=?,slug=?,parent_id=?,sort_order=?,is_active=? WHERE id=?",(name,slug,parent,order,int(bool(active)),cid))
                    except sqlite3.IntegrityError: raise APIError(409,"Slug danh mục đã tồn tại hoặc danh mục còn sản phẩm liên quan")
                    self.audit(db,actor,'category.update','category',cid)
                return self.send_json(200,{"ok":True})
            if path.startswith('/api/admin/users/'):
                actor=self.current_user(True,True); uid=path.rsplit('/',1)[-1]; role=data.get('role')
                if role not in ('customer','seller','admin'): raise APIError(400,"Vai trò không hợp lệ")
                with connect() as db:
                    if not db.execute("SELECT 1 FROM users WHERE id=?",(uid,)).fetchone(): raise APIError(404,"Không tìm thấy tài khoản")
                    if role=='seller' and not db.execute("SELECT 1 FROM seller_profiles WHERE user_id=? AND status='approved'",(uid,)).fetchone(): raise APIError(409,"Chỉ có thể cấp vai trò người bán đã được duyệt")
                    db.execute("UPDATE users SET role=? WHERE id=?",(role,uid)); self.audit(db,actor,'user.role','user',uid,role)
                return self.send_json(200,{"ok":True,"role":role})
            if path.startswith('/api/seller/order-items/'):
                actor=self.require_role('seller'); item_id=path.rsplit('/',1)[-1]; status=data.get('status')
                if status not in ('Đang xử lý','Đang giao'): raise APIError(400,"Trạng thái xử lý không hợp lệ")
                with connect() as db:
                    cur=db.execute("UPDATE order_items SET fulfillment_status=? WHERE id=? AND product_id IN (SELECT id FROM products WHERE owner_id=?) AND order_id IN (SELECT id FROM orders WHERE status NOT IN ('Đã hủy','Hoàn tất'))",(status,item_id,actor['id']))
                    if not cur.rowcount: raise APIError(404,"Không tìm thấy dòng đơn thuộc quyền người bán")
                return self.send_json(200,{"ok":True,"status":status})
            if path.startswith('/api/admin/products/'):
                actor=self.current_user(True,True); pid=path.rsplit('/',1)[-1]; status=data.get('status'); reason=safe_product_text(data.get('reason',''),500,'Lý do kiểm duyệt')
                if status not in ('approved','rejected'): raise APIError(400,"Trạng thái không hợp lệ")
                with connect() as db:
                    product=db.execute("SELECT stock FROM products WHERE id=? AND status='pending' AND lifecycle_status='pending_review'",(pid,)).fetchone()
                    if not product: raise APIError(404,"Sản phẩm chờ duyệt không tồn tại")
                    lifecycle='active' if status=='approved' and product['stock']>0 else ('out_of_stock' if status=='approved' else 'rejected')
                    cur=db.execute("UPDATE products SET status=?,lifecycle_status=?,badge=?,updated_at=? WHERE id=? AND status='pending'",(status,lifecycle,'Đã kiểm duyệt' if status=='approved' else 'Đã từ chối',int(time.time()),pid))
                    if not cur.rowcount: raise APIError(404,"Sản phẩm chờ duyệt không tồn tại")
                    db.execute("INSERT INTO product_history(product_id,actor_id,action,snapshot_json,created_at) VALUES(?,?,?,?,?)",(pid,actor['id'],'moderation.'+status,json.dumps({"reason":reason,"lifecycle_status":lifecycle},ensure_ascii=False),int(time.time())))
                    self.audit(db,actor,'product.'+status,'product',pid,reason)
                return self.send_json(200,{"ok":True,"status":status,"lifecycle_status":lifecycle})
            if path.startswith('/api/admin/payments/'):
                actor=self.current_user(True,True); oid=path.rsplit('/',1)[-1]; note=str(data.get('note','')).strip()
                if data.get('payment_status')!='paid' or len(note)<8 or len(note)>300: raise APIError(400,"Cần ghi căn cứ thu COD hoặc đối soát chuyển khoản (tối thiểu 8 ký tự)")
                with connect() as db:
                    db.execute("BEGIN IMMEDIATE"); row=db.execute("SELECT payment,payment_status,status FROM orders WHERE id=?",(oid,)).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy đơn hàng")
                    if row['payment']=='COD' and row['status'] not in ('Đang giao','Hoàn tất'): raise APIError(409,"Chỉ xác nhận thu COD khi đơn đang giao hoặc đã giao")
                    if row['payment'] not in ('COD','VNPAY_QR') or row['status']=='Đã hủy': raise APIError(409,"Không thể xác nhận khoản thanh toán của đơn này")
                    if row['payment_status']=='paid': return self.send_json(200,{"ok":True,"payment_status":"paid","idempotent_replay":True})
                    now=int(time.time()); db.execute("UPDATE orders SET payment_status='paid' WHERE id=?",(oid,))
                    source='admin_cod_collection' if row['payment']=='COD' else 'admin_qr_transfer_reconciliation'
                    db.execute("INSERT INTO payment_status_history(order_id,payment_status,actor_id,source,note,created_at) VALUES(?,'paid',?,?,?,?)",(oid,actor['id'],source,note,now))
                    self.audit(db,actor,'payment.'+('cod_collected' if row['payment']=='COD' else 'qr_transfer_reconciled'),'order',oid,note)
                return self.send_json(200,{"ok":True,"payment_status":"paid"})
            if path.startswith('/api/admin/orders/'):
                self.current_user(True,True); oid=path.rsplit('/',1)[-1]; status=data.get('status')
                if status not in ('Đang xử lý','Đang giao','Hoàn tất','Đã hủy'): raise APIError(400,"Trạng thái không hợp lệ")
                with connect() as db:
                    row=db.execute("SELECT total,shipping_fee,status,user_id FROM orders WHERE id=?",(oid,)).fetchone()
                    if not row: raise APIError(404,"Không tìm thấy đơn")
                    allowed={'Đang xử lý':('Đang xử lý','Đang giao','Hoàn tất','Đã hủy'),'Đang giao':('Đang giao','Hoàn tất','Đã hủy'),'Hoàn tất':('Hoàn tất',),'Đã hủy':('Đã hủy',)}
                    if status not in allowed.get(row['status'],()): raise APIError(409,"Không thể chuyển đơn sang trạng thái này")
                    db.execute("UPDATE orders SET status=?,points_awarded=CASE WHEN ?='Hoàn tất' THEN 1 ELSE points_awarded END WHERE id=?",(status,status,oid))
                    rental_state={'Đang xử lý':'requested','Đang giao':'handed_out','Hoàn tất':'returned','Đã hủy':'cancelled'}
                    db.execute("UPDATE rental_reservations SET status=? WHERE order_id=? AND status NOT IN ('returned','cancelled')",(rental_state[status],oid))
                    if status=='Hoàn tất' and row['status']!='Hoàn tất':
                        amount=max(0,row['total']-row['shipping_fee'])//10000
                        if amount: db.execute("INSERT OR IGNORE INTO points_ledger(user_id,points,event_type,reference_type,reference_id,note,created_at) VALUES(?,?,'earn','order',?,?,?)",(row['user_id'],amount,oid,'Tích điểm đơn hàng hoàn tất',int(time.time())))
                        items=db.execute("SELECT oi.id,oi.quantity,p.item_type FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?",(oid,)).fetchall()
                        for item in items:
                            factor=db.execute("SELECT * FROM impact_factors WHERE item_type=? AND active=1 ORDER BY version DESC LIMIT 1",(item['item_type'],)).fetchone()
                            if factor:
                                db.execute("INSERT OR IGNORE INTO impact_snapshots(order_item_id,factor_id,factor_value,unit,source_name,source_url,estimated_value,created_at) VALUES(?,?,?,?,?,?,?,?)",(item['id'],factor['id'],factor['factor_value'],factor['unit'],factor['source_name'],factor['source_url'],factor['factor_value']*item['quantity'],int(time.time())))
                    if status!=row['status']: db.execute("INSERT INTO order_status_history(order_id,status,actor_id,note,created_at) VALUES(?,?,?,?,?)",(oid,status,self.current_user(True)['id'],'Quản trị viên cập nhật trạng thái',int(time.time())))
                if status!=row['status']:
                    subject,body=email_templates.order_status(oid,status); self.queue_email(row['user_id'],subject,body)
                return self.send_json(200,{"ok":True,"status":status})
            raise APIError(404,"Không tìm thấy API")
        except APIError as e:self.send_json(e.status,{"error":e.message})
        except Exception as e: print("API error:",repr(e)); self.send_json(500,{"error":"Lỗi máy chủ"})

def main():
    if os.environ.get('RELOOP_ENV','development').lower()=='production' and not COOKIE_SECURE:
        raise SystemExit('Production mode requires RELOOP_COOKIE_SECURE=1 and an HTTPS reverse proxy.')
    init_db()
    print(f"ReLoop Market running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
