CREATE TABLE IF NOT EXISTS support_requests(
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 order_id TEXT REFERENCES orders(id) ON DELETE RESTRICT,
 category TEXT NOT NULL CHECK(category IN ('complaint','order','product','payment','other')),
 subject TEXT NOT NULL CHECK(length(subject) BETWEEN 4 AND 120),
 details TEXT NOT NULL CHECK(length(details) BETWEEN 10 AND 2000),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','resolved','rejected')),
 admin_note TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL,
 updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_support_user_created ON support_requests(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_queue ON support_requests(status,created_at);
