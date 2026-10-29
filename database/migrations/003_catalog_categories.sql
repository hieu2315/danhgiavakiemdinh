CREATE TABLE IF NOT EXISTS categories(
 id INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 slug TEXT NOT NULL UNIQUE,
 parent_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
 sort_order INTEGER NOT NULL DEFAULT 0,
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at INTEGER NOT NULL
);
ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id);
ALTER TABLE products ADD COLUMN item_type TEXT NOT NULL DEFAULT 'used' CHECK(item_type IN ('used','recycled'));
ALTER TABLE products ADD COLUMN rental_price_day INTEGER NOT NULL DEFAULT 0;
INSERT OR IGNORE INTO categories(name,slug,parent_id,sort_order,created_at) VALUES
 ('Điện tử','dien-tu',NULL,1,unixepoch()),('Thời trang','thoi-trang',NULL,2,unixepoch()),('Đồ gia dụng','do-gia-dung',NULL,3,unixepoch()),('Sách và học tập','sach-hoc-tap',NULL,4,unixepoch()),('Sản phẩm tái chế','san-pham-tai-che',NULL,5,unixepoch()),('Cho thuê','cho-thue',NULL,6,unixepoch());
INSERT OR IGNORE INTO categories(name,slug,parent_id,sort_order,created_at)
 SELECT child.name,child.slug,parent.id,child.sort_order,unixepoch() FROM (
  SELECT 'Điện thoại' name,'dien-thoai' slug,'dien-tu' parent,1 sort_order UNION ALL SELECT 'Laptop','laptop','dien-tu',2 UNION ALL SELECT 'Phụ kiện','phu-kien','dien-tu',3 UNION ALL
  SELECT 'Quần áo','quan-ao','thoi-trang',1 UNION ALL SELECT 'Giày dép','giay-dep','thoi-trang',2 UNION ALL SELECT 'Túi xách','tui-xach','thoi-trang',3 UNION ALL
  SELECT 'Nội thất','noi-that','do-gia-dung',1 UNION ALL SELECT 'Thiết bị nhà bếp','nha-bep','do-gia-dung',2 UNION ALL SELECT 'Đồ trang trí','trang-tri','do-gia-dung',3 UNION ALL
  SELECT 'Sách cũ','sach-cu','sach-hoc-tap',1 UNION ALL SELECT 'Dụng cụ học tập','dung-cu-hoc-tap','sach-hoc-tap',2 UNION ALL
  SELECT 'Đồ thủ công','do-thu-cong','san-pham-tai-che',1 UNION ALL SELECT 'Đồ trang trí tái chế','trang-tri-tai-che','san-pham-tai-che',2 UNION ALL SELECT 'Tái chế nhựa/giấy','nhua-giay','san-pham-tai-che',3 UNION ALL
  SELECT 'Thiết bị học tập','thue-hoc-tap','cho-thue',1 UNION ALL SELECT 'Thiết bị điện tử','thue-dien-tu','cho-thue',2 UNION ALL SELECT 'Đồ gia dụng cho thuê','thue-gia-dung','cho-thue',3
 ) child JOIN categories parent ON parent.slug=child.parent;
UPDATE products SET category_id=(SELECT id FROM categories WHERE slug=CASE category WHEN 'Điện tử' THEN 'dien-tu' WHEN 'Thời trang' THEN 'thoi-trang' WHEN 'Đồ gia dụng' THEN 'do-gia-dung' WHEN 'Nội thất' THEN 'do-gia-dung' ELSE 'san-pham-tai-che' END),item_type=CASE WHEN category='Tái chế' THEN 'recycled' ELSE 'used' END,rental_price_day=CASE WHEN rentable=1 THEN 49000 ELSE 0 END;
CREATE INDEX IF NOT EXISTS idx_categories_parent_sort ON categories(parent_id,is_active,sort_order);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id,status);
