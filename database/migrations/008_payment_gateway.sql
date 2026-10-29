ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
ALTER TABLE orders ADD COLUMN payment_expires_at INTEGER;
UPDATE orders SET payment_status=CASE WHEN payment='VNPAY' THEN 'pending' ELSE 'unpaid' END;

CREATE TABLE checkout_idempotency(
 user_id INTEGER NOT NULL REFERENCES users(id),
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
 created_at INTEGER NOT NULL,
 PRIMARY KEY(user_id,idempotency_key)
);

CREATE TABLE payment_transactions(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES orders(id),
 provider TEXT NOT NULL,
 txn_ref TEXT NOT NULL UNIQUE,
 amount INTEGER NOT NULL CHECK(amount>=0),
 currency TEXT NOT NULL DEFAULT 'VND',
 status TEXT NOT NULL CHECK(status IN ('pending','success','failed','cancelled','expired','late_success')),
 provider_transaction_no TEXT,
 response_code TEXT,
 created_at INTEGER NOT NULL,
 updated_at INTEGER NOT NULL
);
CREATE INDEX idx_payment_transactions_order ON payment_transactions(order_id,created_at DESC);

CREATE TABLE payment_status_history(
 id INTEGER PRIMARY KEY,
 order_id TEXT NOT NULL REFERENCES orders(id),
 payment_status TEXT NOT NULL,
 actor_id INTEGER REFERENCES users(id),
 source TEXT NOT NULL,
 note TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL
);
CREATE INDEX idx_payment_history_order ON payment_status_history(order_id,created_at,id);
