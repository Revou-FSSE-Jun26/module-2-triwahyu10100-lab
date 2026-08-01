-- ============================================================
-- RevoShop Database Schema — Checkpoint 1
-- File: schema.sql
-- Description: Core table definitions for the RevoShop store.
-- Run this against an empty database, e.g. revoshop_sql.
-- ============================================================

-- Drop tables if re-running this script during development.
-- Order matters because of foreign key dependencies.
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ------------------------------------------------------------
-- Table: users
-- Account records. NOTE: no "role" column yet on purpose —
-- that arrives in Checkpoint 2 as a live schema migration.
-- ------------------------------------------------------------
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    phone         VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Table: categories
-- Product categories (e.g. Electronics, Apparel).
-- ------------------------------------------------------------
CREATE TABLE categories (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description   TEXT,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Table: products
-- Store items. Each product belongs to exactly one category.
-- ------------------------------------------------------------
CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    category_id   INTEGER        NOT NULL,
    product_name  VARCHAR(150)   NOT NULL,
    description   TEXT,
    price         NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock_quantity INTEGER       NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    sku           VARCHAR(50)    NOT NULL UNIQUE,
    created_at    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES categories (category_id)
        ON DELETE RESTRICT
);

-- ------------------------------------------------------------
-- Table: orders
-- One order is placed by one user; an order can contain many
-- products via the order_items junction table below.
-- ------------------------------------------------------------
CREATE TABLE orders (
    order_id      SERIAL PRIMARY KEY,
    user_id       INTEGER        NOT NULL,
    order_date    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status        VARCHAR(20)    NOT NULL DEFAULT 'waiting'
                     CHECK (status IN ('waiting', 'paid', 'shipped', 'delivered', 'cancelled')),
    total_amount  NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    shipping_address VARCHAR(255) NOT NULL,

    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE RESTRICT
);

-- ------------------------------------------------------------
-- Table: order_items
-- Junction table implementing the many-to-many relationship
-- between orders and products. Stores a price snapshot at the
-- time of purchase (unit_price) so historical totals stay
-- correct even if a product's price changes later.
-- ------------------------------------------------------------
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INTEGER        NOT NULL,
    product_id    INTEGER        NOT NULL,
    quantity      INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products (product_id)
        ON DELETE RESTRICT,

    -- Prevent the exact same product being added as a duplicate
    -- line item on the same order (increase quantity instead).
    CONSTRAINT uq_order_product UNIQUE (order_id, product_id)
);

-- ------------------------------------------------------------
-- Helpful indexes for common lookups / joins
-- ------------------------------------------------------------
CREATE INDEX idx_products_category_id ON products (category_id);
CREATE INDEX idx_orders_user_id       ON orders (user_id);
CREATE INDEX idx_order_items_order_id ON order_items (order_id);
CREATE INDEX idx_order_items_product_id ON order_items (product_id);
