CREATE TABLE IF NOT EXISTS product_condition_assessments(
 product_id TEXT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
 appearance_score INTEGER NOT NULL CHECK(appearance_score BETWEEN 0 AND 100),
 functionality TEXT NOT NULL CHECK(functionality IN ('working','partial','not_working')),
 wear_level TEXT NOT NULL CHECK(wear_level IN ('low','medium','high')),
 accessories TEXT NOT NULL CHECK(accessories IN ('complete','partial','none')),
 usage_years INTEGER NOT NULL CHECK(usage_years BETWEEN 0 AND 50),
 score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
 recycled_material_pct INTEGER CHECK(recycled_material_pct BETWEEN 0 AND 100),
 updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS points_ledger(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 points INTEGER NOT NULL CHECK(points<>0),
 event_type TEXT NOT NULL CHECK(event_type IN ('earn','reversal','redeem')),
 reference_type TEXT NOT NULL,
 reference_id TEXT NOT NULL,
 note TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL,
 UNIQUE(user_id,event_type,reference_type,reference_id)
);
CREATE INDEX IF NOT EXISTS idx_points_ledger_user ON points_ledger(user_id,created_at DESC);
INSERT OR IGNORE INTO points_ledger(user_id,points,event_type,reference_type,reference_id,note,created_at)
 SELECT user_id,CAST(total/10000 AS INTEGER),'earn','order',id,'Điểm đơn hàng hoàn tất (chuyển dữ liệu)',created_at FROM orders WHERE points_awarded=1 AND total>=10000;
CREATE TABLE IF NOT EXISTS rental_reservations(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
 product_id TEXT NOT NULL REFERENCES products(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 start_date TEXT NOT NULL,
 end_date TEXT NOT NULL,
 quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity>0),
 status TEXT NOT NULL DEFAULT 'requested' CHECK(status IN ('requested','confirmed','handed_out','returned','cancelled')),
 deposit_amount INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rental_dates ON rental_reservations(product_id,start_date,end_date,status);
ALTER TABLE subscriptions ADD COLUMN cadence TEXT NOT NULL DEFAULT 'monthly';
ALTER TABLE subscriptions ADD COLUMN starts_at TEXT;
ALTER TABLE subscriptions ADD COLUMN next_due_at TEXT;
ALTER TABLE subscriptions ADD COLUMN cancelled_at INTEGER;
ALTER TABLE products ADD COLUMN rental_stock INTEGER NOT NULL DEFAULT 1 CHECK(rental_stock>=0);
CREATE TABLE IF NOT EXISTS impact_factors(
 id INTEGER PRIMARY KEY,
 item_type TEXT NOT NULL CHECK(item_type IN ('used','recycled')),
 factor_value REAL NOT NULL CHECK(factor_value>=0),
 unit TEXT NOT NULL,
 scope TEXT NOT NULL,
 source_name TEXT NOT NULL,
 source_url TEXT NOT NULL,
 version INTEGER NOT NULL,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at INTEGER NOT NULL,
 UNIQUE(item_type,version)
);
CREATE TABLE IF NOT EXISTS impact_snapshots(
 order_item_id INTEGER PRIMARY KEY REFERENCES order_items(id) ON DELETE CASCADE,
 factor_id INTEGER NOT NULL REFERENCES impact_factors(id),
 factor_value REAL NOT NULL,
 unit TEXT NOT NULL,
 source_name TEXT NOT NULL,
 source_url TEXT NOT NULL,
 estimated_value REAL NOT NULL,
 created_at INTEGER NOT NULL
);
