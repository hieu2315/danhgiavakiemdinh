CREATE TABLE login_attempt_buckets(
 bucket_key TEXT PRIMARY KEY,
 failures INTEGER NOT NULL DEFAULT 0,
 window_started INTEGER NOT NULL,
 blocked_until INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE security_events(
 id INTEGER PRIMARY KEY,
 event_type TEXT NOT NULL,
 ip_hash TEXT NOT NULL DEFAULT '',
 account_hash TEXT NOT NULL DEFAULT '',
 user_id INTEGER REFERENCES users(id),
 created_at INTEGER NOT NULL
);
CREATE INDEX idx_security_events_created ON security_events(created_at DESC);

CREATE TABLE upload_assets(
 id INTEGER PRIMARY KEY,
 path TEXT NOT NULL UNIQUE,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
 mime_type TEXT NOT NULL,
 size INTEGER NOT NULL CHECK(size>0 AND size<=3000000),
 created_at INTEGER NOT NULL
);
CREATE INDEX idx_upload_assets_owner_created ON upload_assets(owner_id,created_at DESC);
