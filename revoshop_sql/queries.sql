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
    product_id,
    product_name,
    price,
    stock_quantity
FROM products
WHERE category_id = 1
  AND stock_quantity > 0
ORDER BY price DESC
LIMIT 3;


-- ------------------------------------------------------------
-- 2. All orders placed by a specific user, most recent first.
-- ------------------------------------------------------------
SELECT
    order_id,
    order_date,
    status,
    total_amount
FROM orders
WHERE user_id = 1
ORDER BY order_date DESC;

-- ------------------------------------------------------------
-- 3. Full line-item detail for a single order (join across
-- orders -> order_items -> products).
-- ------------------------------------------------------------
SELECT
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    (quantity * unit_price) AS line_total
FROM order_items
WHERE order_id = 1;


-- ------------------------------------------------------------
-- 4. Best-selling products by total quantity sold (aggregation).
-- ------------------------------------------------------------
SELECT
    product_id,
    SUM(quantity) AS total_units_sold
FROM order_items
GROUP BY product_id
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
