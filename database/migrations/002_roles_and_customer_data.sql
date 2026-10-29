CREATE TABLE IF NOT EXISTS seller_profiles(
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 business_type TEXT NOT NULL CHECK(business_type IN ('c2c','b2c')),
 display_name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS addresses(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 recipient TEXT NOT NULL,
 phone TEXT NOT NULL,
 address TEXT NOT NULL,
 is_default INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites(
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,product_id)
);
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY,
 actor_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL,
 entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 details TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL
);
ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 10 CHECK(stock>=0);
ALTER TABLE order_items ADD COLUMN fulfillment_status TEXT NOT NULL DEFAULT 'Đang xử lý';
CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
