-- ============================================================
-- RevoShop Sample Queries — Checkpoint 1
-- File: queries.sql
-- Demonstrates common read patterns against the seeded data.
-- ============================================================

-- ------------------------------------------------------------
-- 1. REQUIRED: combines WHERE + ORDER BY + LIMIT
-- Find the 3 most expensive in-stock Electronics products.
-- ------------------------------------------------------------
SELECT
    p.product_id,
    p.product_name,
    p.price,
    p.stock_quantity
FROM products p
JOIN categories c ON c.category_id = p.category_id
WHERE c.category_name = 'Electronics'
  AND p.stock_quantity > 0
ORDER BY p.price DESC
LIMIT 3;

-- ------------------------------------------------------------
-- 2. All orders placed by a specific user, most recent first.
-- ------------------------------------------------------------
SELECT
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount
FROM orders o
JOIN users u ON u.user_id = o.user_id
WHERE u.email = 'siti.rahayu@example.com'
ORDER BY o.order_date DESC;

-- ------------------------------------------------------------
-- 3. Full line-item detail for a single order (join across
-- orders -> order_items -> products).
-- ------------------------------------------------------------
SELECT
    oi.order_item_id,
    p.product_name,
    oi.quantity,
    oi.unit_price,
    (oi.quantity * oi.unit_price) AS line_total
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
WHERE oi.order_id = 1;

-- ------------------------------------------------------------
-- 4. Best-selling products by total quantity sold (aggregation).
-- ------------------------------------------------------------
SELECT
    p.product_name,
    COALESCE(SUM(oi.quantity), 0) AS total_units_sold,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_revenue
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.product_name
ORDER BY total_units_sold DESC;

-- ------------------------------------------------------------
-- 5. Products that are low on stock (below 40 units), cheapest
-- first, top 5 only — another WHERE + ORDER BY + LIMIT example.
-- ------------------------------------------------------------
SELECT
    product_name,
    stock_quantity,
    price
FROM products
WHERE stock_quantity < 40
ORDER BY price ASC
LIMIT 5;

-- ------------------------------------------------------------
-- 6. Count of orders per status.
-- ------------------------------------------------------------
SELECT
    status,
    COUNT(*) AS order_count
FROM orders
GROUP BY status
ORDER BY order_count DESC;
