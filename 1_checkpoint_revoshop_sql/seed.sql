-- users
INSERT INTO users (first_name, last_name, email, phone, password_hash) VALUES
('Siti',    'Rahayu',   'siti.rahayu@example.com',   '+62-812-1111-2222', '$2b$12$examplehashuser0001'),
('Budi',    'Santoso',  'budi.santoso@example.com',  '+62-813-2222-3333', '$2b$12$examplehashuser0002'),
('Chelsea', 'Wijaya',   'chelsea.wijaya@example.com','+62-814-3333-4444', '$2b$12$examplehashuser0003'),
('Andi',    'Prasetyo', 'andi.prasetyo@example.com', '+62-815-4444-5555', '$2b$12$examplehashuser0004'),
('Maria',   'Simanjuntak','maria.simanjuntak@example.com','+62-816-5555-6666','$2b$12$examplehashuser0005'),
('Rudi',    'Hartono',  'rudi.hartono@example.com',  NULL,                 '$2b$12$examplehashuser0006');

-- categories
INSERT INTO categories (category_name, description) VALUES
('Electronics',      'Gadgets, computers, and electronic accessories'),
('Apparel',           'Clothing and fashion items for all ages'),
('Home & Kitchen',    'Furniture, appliances, and kitchenware'),
('Books',             'Fiction, non-fiction, and educational books'),
('Sports & Outdoors',  'Equipment and gear for sports and outdoor activities');

-- products (dengan slug, images, created_at, updated_at sesuai skema terbaru)
INSERT INTO products (category_id, product_name, slug, description, price, stock_quantity, sku, images, created_at, updated_at) VALUES
(1, 'Wireless Bluetooth Headphones', 'wireless-bluetooth-headphones', 'Over-ear headphones with active noise cancellation', 799000.00, 50, 'ELEC-HEAD-001', '[]', NOW(), NOW()),
(1, 'USB-C Fast Charger 65W',        'usb-c-fast-charger-65w',        'GaN fast charger compatible with laptops and phones', 249000.00, 120, 'ELEC-CHRG-002', '[]', NOW(), NOW()),
(1, 'Mechanical Keyboard RGB',       'mechanical-keyboard-rgb',       'Tactile switches with per-key RGB lighting', 550000.00, 35, 'ELEC-KEYB-003', '[]', NOW(), NOW()),
(2, 'Cotton Crewneck T-Shirt',       'cotton-crewneck-t-shirt',       'Unisex 100% cotton t-shirt, various colors', 89000.00, 200, 'APRL-TSHT-001', '[]', NOW(), NOW()),
(2, 'Denim Jacket',                  'denim-jacket',                  'Classic fit denim jacket for men and women', 349000.00, 60, 'APRL-JCKT-002', '[]', NOW(), NOW()),
(3, 'Non-Stick Frying Pan 28cm',     'non-stick-frying-pan-28cm',     'Durable non-stick frying pan with ergonomic handle', 175000.00, 80, 'HOME-PAN-001', '[]', NOW(), NOW()),
(3, 'Electric Kettle 1.7L',          'electric-kettle-1-7l',          'Stainless steel electric kettle with auto shut-off', 210000.00, 45, 'HOME-KETL-002', '[]', NOW(), NOW()),
(4, 'Atomic Habits (Paperback)',     'atomic-habits-paperback',       'Bestselling book on building good habits', 120000.00, 100, 'BOOK-ATHB-001', '[]', NOW(), NOW()),
(4, 'The Pragmatic Programmer',      'the-pragmatic-programmer',      'Classic software engineering reference book', 275000.00, 40, 'BOOK-PPRG-002', '[]', NOW(), NOW()),
(5, 'Yoga Mat Premium',              'yoga-mat-premium',              'Non-slip 6mm yoga mat with carry strap', 165000.00, 70, 'SPRT-YOGA-001', '[]', NOW(), NOW());

-- orders
INSERT INTO orders (user_id, order_date, status, total_amount, shipping_address) VALUES
(1, '2026-06-02 09:15:00', 'delivered', 1048000.00, 'Jl. Merdeka No. 10, Medan, North Sumatra'),
(2, '2026-06-10 14:32:00', 'shipped',    699000.00, 'Jl. Sudirman No. 45, Jakarta Selatan'),
(3, '2026-06-18 11:05:00', 'paid',       485000.00, 'Jl. Gatot Subroto No. 8, Bandung'),
(1, '2026-07-01 16:47:00', 'waiting',    120000.00, 'Jl. Merdeka No. 10, Medan, North Sumatra'),
(4, '2026-07-15 10:20:00', 'cancelled',  550000.00, 'Jl. Diponegoro No. 22, Surabaya'),
(5, '2026-07-25 13:00:00', 'delivered',  505000.00, 'Jl. Ahmad Yani No. 5, Medan, North Sumatra');

-- order_items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 799000.00),
(1, 2, 1, 249000.00),
(2, 3, 1, 550000.00),
(2, 8, 1, 120000.00),
(2, 4, 1, 29000.00),
(3, 5, 1, 349000.00),
(3, 6, 1, 136000.00),
(4, 8, 1, 120000.00),
(5, 3, 1, 550000.00),
(6, 7, 1, 210000.00),
(6, 10, 1, 165000.00),
(6, 9, 1, 130000.00);
