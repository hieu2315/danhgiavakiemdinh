CREATE TABLE IF NOT EXISTS order_status_history(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 status TEXT NOT NULL,
 actor_id INTEGER REFERENCES users(id),
 note TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_history_order ON order_status_history(order_id,created_at);
