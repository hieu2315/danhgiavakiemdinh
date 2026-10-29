CREATE TABLE IF NOT EXISTS reviews(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
 body TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 seller_reply TEXT,
 replied_at INTEGER,
 created_at INTEGER NOT NULL,
 UNIQUE(order_id,product_id,user_id)
);
CREATE TABLE IF NOT EXISTS vouchers(
 id INTEGER PRIMARY KEY,
 code TEXT NOT NULL UNIQUE COLLATE NOCASE,
 discount_type TEXT NOT NULL CHECK(discount_type IN ('percent','fixed')),
 value INTEGER NOT NULL CHECK(value>0),
 min_order INTEGER NOT NULL DEFAULT 0,
 max_discount INTEGER,
 starts_at INTEGER NOT NULL,
 ends_at INTEGER NOT NULL,
 usage_limit INTEGER,
 per_user_limit INTEGER NOT NULL DEFAULT 1,
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS voucher_redemptions(
 id INTEGER PRIMARY KEY,
 voucher_id INTEGER NOT NULL REFERENCES vouchers(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
 discount INTEGER NOT NULL,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_outbox(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL,
 subject TEXT NOT NULL,
 body TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed')),
 error TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL,
 sent_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reviews_product_status ON reviews(product_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_voucher_redemptions_user ON voucher_redemptions(voucher_id,user_id);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON notification_outbox(status,created_at);
