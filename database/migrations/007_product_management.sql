ALTER TABLE products ADD COLUMN slug TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN short_description TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN specifications_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE products ADD COLUMN seller_type TEXT NOT NULL DEFAULT 'c2c' CHECK(seller_type IN ('c2c','b2c'));
ALTER TABLE products ADD COLUMN shipping_policy TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN return_policy TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle_status IN ('draft','pending_review','active','hidden','out_of_stock','rejected','archived'));
ALTER TABLE products ADD COLUMN updated_at INTEGER NOT NULL DEFAULT 0;
UPDATE products SET slug=id,short_description=substr(description,1,180),updated_at=created_at,
 lifecycle_status=CASE WHEN status='pending' THEN 'pending_review' WHEN status='rejected' THEN 'rejected' WHEN stock=0 THEN 'out_of_stock' ELSE 'active' END;
UPDATE products SET seller_type=COALESCE((SELECT business_type FROM seller_profiles WHERE seller_profiles.user_id=products.owner_id),'c2c');
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_slug ON products(slug) WHERE slug<>'';
CREATE INDEX IF NOT EXISTS idx_products_owner_lifecycle ON products(owner_id,lifecycle_status,updated_at DESC);
CREATE TABLE IF NOT EXISTS product_images(
 id INTEGER PRIMARY KEY,
 product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 image_path TEXT NOT NULL,
 alt_text TEXT NOT NULL DEFAULT '',
 sort_order INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL,
 UNIQUE(product_id,image_path)
);
CREATE TABLE IF NOT EXISTS product_history(
 id INTEGER PRIMARY KEY,
 product_id TEXT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
 actor_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL,
 snapshot_json TEXT NOT NULL,
 created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_history_product ON product_history(product_id,created_at DESC);
