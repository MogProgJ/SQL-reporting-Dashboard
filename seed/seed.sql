-- =============================================================
-- SQL Reporting Dashboard — Seed Script
-- Idempotent: safe to rerun (drops and recreates tables).
-- =============================================================
-- ---- schema ------------------------------------------------
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
CREATE TABLE customers (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  segment TEXT NOT NULL DEFAULT 'Standard',
  city TEXT NOT NULL DEFAULT 'Unknown'
);
CREATE TABLE categories (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE products (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category_id BIGINT NOT NULL REFERENCES categories(id),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0)
);
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  status TEXT NOT NULL DEFAULT 'completed',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE order_items (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id),
  product_id BIGINT NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0)
);
-- ---- customers (30) ----------------------------------------
INSERT INTO customers (name, segment, city)
VALUES ('Acme Foods', 'Enterprise', 'New York'),
  ('Bluebird Cafe', 'SMB', 'Chicago'),
  ('Northside Deli', 'SMB', 'Portland'),
  ('Summit Catering', 'Enterprise', 'Denver'),
  ('Lakefront Bistro', 'Mid-Market', 'Chicago'),
  ('Metro Grocers', 'Enterprise', 'New York'),
  ('Pine Street Bakery', 'SMB', 'Seattle'),
  ('Harbor Fish Co', 'Mid-Market', 'Boston'),
  (
    'Redwood Provisions',
    'Enterprise',
    'San Francisco'
  ),
  ('Valley Ranch Supply', 'Mid-Market', 'Austin'),
  ('Downtown Pantry', 'SMB', 'Portland'),
  ('Coastal Kitchen', 'Mid-Market', 'Miami'),
  ('Prairie Farms LLC', 'Enterprise', 'Denver'),
  ('Sunrise Juice Bar', 'SMB', 'Austin'),
  ('Silver Spoon Diner', 'SMB', 'Chicago'),
  ('Iron Gate Grill', 'Mid-Market', 'Boston'),
  ('The Flour Shop', 'SMB', 'Seattle'),
  (
    'Golden Leaf Tea',
    'SMB',
    'San Francisco'
  ),
  ('Capitol Catering', 'Enterprise', 'New York'),
  ('Alpine Organics', 'Mid-Market', 'Denver'),
  (
    'Bay Area Bites',
    'Mid-Market',
    'San Francisco'
  ),
  ('Crossroads Deli', 'SMB', 'Austin'),
  ('Evergreen Eats', 'SMB', 'Seattle'),
  ('Magnolia Market', 'Mid-Market', 'Miami'),
  ('Stonewall Kitchen', 'Enterprise', 'Boston'),
  ('Wildflower Bakery', 'SMB', 'Portland'),
  ('Cedar & Salt', 'Mid-Market', 'Chicago'),
  ('Hudson Provisions', 'Enterprise', 'New York'),
  ('Peachtree Pantry', 'SMB', 'Miami'),
  ('Blue Ridge Supply', 'Mid-Market', 'Denver');
-- ---- categories (8) ----------------------------------------
INSERT INTO categories (name)
VALUES ('Produce'),
  ('Dairy'),
  ('Bakery'),
  ('Beverages'),
  ('Meat & Seafood'),
  ('Snacks'),
  ('Frozen'),
  ('Pantry Staples');
-- ---- products (30) -----------------------------------------
INSERT INTO products (name, category_id, unit_price_cents)
VALUES ('Organic Bananas', 1, 149),
  ('Roma Tomatoes 1lb', 1, 299),
  ('Baby Spinach 5oz', 1, 349),
  ('Avocados (3-pack)', 1, 499),
  ('Whole Milk 1gal', 2, 459),
  ('Cheddar Cheese Block', 2, 649),
  ('Greek Yogurt 32oz', 2, 579),
  ('Butter Unsalted 1lb', 2, 499),
  ('Sourdough Loaf', 3, 549),
  ('Croissants (6-pack)', 3, 799),
  ('Whole Wheat Bread', 3, 429),
  ('Cinnamon Rolls (4-pack)', 3, 699),
  ('Cold Brew Coffee 32oz', 4, 899),
  ('Orange Juice 52oz', 4, 449),
  ('Sparkling Water 12-pack', 4, 599),
  ('Green Tea Box (20ct)', 4, 399),
  ('Chicken Breast 2lb', 5, 1099),
  ('Atlantic Salmon 1lb', 5, 1299),
  ('Ground Beef 1lb', 5, 799),
  ('Shrimp 1lb Frozen', 5, 1199),
  ('Trail Mix 16oz', 6, 699),
  ('Tortilla Chips 13oz', 6, 449),
  ('Dark Chocolate Bar', 6, 349),
  ('Mixed Nuts 24oz', 6, 999),
  ('Frozen Pizza Margherita', 7, 699),
  ('Frozen Berries Mix 1lb', 7, 499),
  ('Ice Cream Pint', 7, 549),
  ('Olive Oil 500ml', 8, 899),
  ('Jasmine Rice 5lb', 8, 749),
  ('Pasta Penne 1lb', 8, 199);
-- ---- orders + order_items ----------------------------------
-- Generate ~150 orders spread over the last ~6 months with
-- 2-5 items each using a procedural block.
DO $$
DECLARE v_order_id BIGINT;
v_cust_id BIGINT;
v_prod_id BIGINT;
v_price INTEGER;
v_status TEXT;
v_items INTEGER;
v_day_offset INTEGER;
statuses TEXT [] := ARRAY ['completed','completed','completed','completed','pending','cancelled'];
BEGIN FOR i IN 1..150 LOOP -- random customer 1-30
v_cust_id := (floor(random() * 30) + 1)::BIGINT;
-- random date in last ~180 days
v_day_offset := floor(random() * 180)::INTEGER;
-- weighted status (mostly completed)
v_status := statuses [floor(random() * array_length(statuses,1))::INT + 1];
INSERT INTO orders (customer_id, status, created_at)
VALUES (
    v_cust_id,
    v_status,
    now() - (v_day_offset || ' days')::INTERVAL - (floor(random() * 12) || ' hours')::INTERVAL
  )
RETURNING id INTO v_order_id;
-- 2-5 items per order
v_items := floor(random() * 4 + 2)::INTEGER;
FOR j IN 1..v_items LOOP v_prod_id := (floor(random() * 30) + 1)::BIGINT;
SELECT unit_price_cents INTO v_price
FROM products
WHERE id = v_prod_id;
INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
VALUES (
    v_order_id,
    v_prod_id,
    floor(random() * 5 + 1)::INTEGER,
    v_price
  );
END LOOP;
END LOOP;
END $$;
