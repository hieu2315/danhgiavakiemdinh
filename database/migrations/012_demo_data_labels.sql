ALTER TABLE orders ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
ALTER TABLE reviews ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0,1));
CREATE INDEX IF NOT EXISTS idx_orders_demo_status_created ON orders(is_demo,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_real_rating ON reviews(product_id,status,is_demo,rating);
