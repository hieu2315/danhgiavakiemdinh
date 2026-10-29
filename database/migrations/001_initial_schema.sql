PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'customer' CHECK(role IN ('customer','seller','admin')),
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products(
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 category TEXT NOT NULL,
 condition TEXT NOT NULL,
 seller TEXT NOT NULL,
 price INTEGER NOT NULL CHECK(price>0),
 emoji TEXT NOT NULL,
 bg TEXT NOT NULL,
 badge TEXT NOT NULL,
 co2 INTEGER NOT NULL DEFAULT 0,
 rentable INTEGER NOT NULL DEFAULT 0,
 description TEXT NOT NULL DEFAULT '',
 owner_id INTEGER REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'approved' CHECK(status IN ('pending','approved','rejected')),
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders(
 id TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 total INTEGER NOT NULL CHECK(total>=0),
 payment TEXT NOT NULL,
 status TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'purchase',
 address TEXT NOT NULL,
 created_at INTEGER NOT NULL,
 points_awarded INTEGER NOT NULL DEFAULT 0,
 provider_reference TEXT
);
CREATE TABLE IF NOT EXISTS order_items(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 product_id TEXT NOT NULL REFERENCES products(id),
 name TEXT NOT NULL,
 price INTEGER NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity>0),
 rental_days INTEGER
);
CREATE TABLE IF NOT EXISTS subscriptions(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 plan TEXT NOT NULL,
 price INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_status_category ON products(status,category);
CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
