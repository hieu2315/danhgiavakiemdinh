INSERT OR IGNORE INTO products(id,name,category,condition,seller,price,emoji,bg,badge,co2,rentable,created_at,description) VALUES
('p13','Đèn đọc sách gỗ phục hồi','Nội thất','Đã qua sử dụng · Tốt','Linh Demo · Hà Nội',240000,'Đèn','#e9e4d9','Mẫu trình diễn',0,1,strftime('%s','now'),'Đèn đọc sách đã qua sử dụng, mô tả mẫu phục vụ trình diễn.'),
('p14','Áo sơ mi cotton second-hand','Thời trang','Đã qua sử dụng · Rất tốt','Linh Demo · Hà Nội',160000,'Áo','#e0e8e8','Mẫu trình diễn',0,0,strftime('%s','now'),'Áo sơ mi đã qua sử dụng, thông tin mẫu cho đồ án.'),
('p15','Bàn trà gỗ nhỏ','Nội thất','Đã qua sử dụng · Tốt','Linh Demo · Hà Nội',520000,'Bàn','#eee5d8','Mẫu trình diễn',0,1,strftime('%s','now'),'Bàn trà cũ, tình trạng và thuộc tính mẫu.'),
('p16','Túi vải canvas tái chế','Tái chế','Mới · Tái chế thủ công','Linh Demo · Hà Nội',125000,'Túi','#e8eadc','Mẫu trình diễn',0,0,strftime('%s','now'),'Túi mẫu từ vải tái sử dụng; không phải chứng nhận vật liệu.'),
('p17','Khay bàn làm từ gỗ thu hồi','Tái chế','Mới · Tái chế thủ công','Xưởng Xanh Demo · Đà Nẵng',210000,'Khay','#e9e3dc','Mẫu trình diễn',0,0,strftime('%s','now'),'Khay demo làm từ vật liệu thu hồi; nội dung minh họa.'),
('p18','Ghế đôn sửa mới','Nội thất','Đã qua sử dụng · Tốt','Xưởng Xanh Demo · Đà Nẵng',390000,'Ghế','#e6eadb','Mẫu trình diễn',0,1,strftime('%s','now'),'Ghế đôn cũ đã sửa chữa, dữ liệu dùng để demo.'),
('p19','Bình nước inox đã dùng','Đồ gia dụng','Đã qua sử dụng · Tốt','Xưởng Xanh Demo · Đà Nẵng',90000,'Bình','#e8e2db','Mẫu trình diễn',0,0,strftime('%s','now'),'Bình mẫu đã qua sử dụng, cần kiểm tra vệ sinh trước khi dùng.'),
('p20','Ví nhỏ từ banner tái sử dụng','Tái chế','Mới · Tái chế thủ công','Xưởng Xanh Demo · Đà Nẵng',175000,'Ví','#e4e4e1','Mẫu trình diễn',0,0,strftime('%s','now'),'Ví demo làm từ banner cũ; tỷ lệ vật liệu không được xác minh.'),
('p21','Máy xay sinh tố đã qua sử dụng','Đồ gia dụng','Đã qua sử dụng · Tốt','Minh Demo · TP. HCM',310000,'Máy','#ede5d7','Mẫu trình diễn',0,0,strftime('%s','now'),'Thiết bị mẫu phục vụ kiểm thử catalog.'),
('p22','Túi đeo chéo vintage','Thời trang','Đã qua sử dụng · Khá','Minh Demo · TP. HCM',225000,'Túi','#edebdf','Mẫu trình diễn',0,0,strftime('%s','now'),'Túi demo có dấu hiệu sử dụng nhẹ.'),
('p23','Giỏ đựng đồ từ nhựa tái sinh','Tái chế','Mới · Tái chế thủ công','Lành Studio Demo · Hà Nội',145000,'Giỏ','#e4e9df','Mẫu trình diễn',0,0,strftime('%s','now'),'Sản phẩm mẫu; thông tin vật liệu dùng để trình diễn, chưa kiểm định.'),
('p24','Máy ảnh compact cũ','Điện tử','Đã qua sử dụng · Tốt','Minh Demo · TP. HCM',850000,'Máy ảnh','#e8dfd3','Mẫu trình diễn',0,1,strftime('%s','now'),'Máy ảnh demo; tình trạng mẫu, hãy kiểm tra trước khi giao dịch.');

INSERT OR IGNORE INTO vouchers(code,discount_type,value,min_order,max_discount,starts_at,ends_at,usage_limit,per_user_limit,is_active,created_at) VALUES
('DEMOXANH','percent',10,100000,50000,unixepoch()-86400,unixepoch()+2592000,100,1,1,unixepoch()),
('DEMOHETHAN','fixed',20000,100000,20000,unixepoch()-2592000,unixepoch()-86400,100,1,1,unixepoch());

-- Values below are illustrative only and deliberately inactive; they must never drive public impact claims.
INSERT OR IGNORE INTO impact_factors(item_type,factor_value,unit,scope,source_name,source_url,version,active,created_at) VALUES
('used',0.1,'kg CO2e (minh họa)','DEMO ONLY: số ngẫu nhiên để minh họa schema, không dùng ước tính hoặc công bố tác động','Giá trị minh họa đồ án — không có căn cứ khoa học','',1,0,unixepoch()),
('recycled',0.05,'kg CO2e (minh họa)','DEMO ONLY: số ngẫu nhiên để minh họa schema, không dùng ước tính hoặc công bố tác động','Giá trị minh họa đồ án — không có căn cứ khoa học','',1,0,unixepoch());

UPDATE products SET stock=1,lifecycle_status='active',status='approved' WHERE id BETWEEN 'p13' AND 'p24';

