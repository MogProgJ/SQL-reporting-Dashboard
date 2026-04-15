-- =============================================================
-- SQL Reporting Dashboard — Seed Script
-- Idempotent: safe to rerun (drops and recreates tables).
-- =============================================================
-- ---- schema ------------------------------------------------
DROP TABLE IF EXISTS flat_metrics CASCADE;
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
-- ---- flat_metrics table ------------------------------------
CREATE TABLE flat_metrics (
  id BIGSERIAL PRIMARY KEY,
  entity TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  year INTEGER,
  score DOUBLE PRECISION,
  rank INTEGER
);
-- ---- flat_metrics demo data (Global Country Indicators) ----
INSERT INTO flat_metrics (entity, year, metric_name, metric_value)
VALUES -- GDP per Capita (USD)
  ('United States', 2021, 'GDP per Capita', 63544),
  ('United States', 2022, 'GDP per Capita', 65280),
  ('United States', 2023, 'GDP per Capita', 66200),
  ('China', 2021, 'GDP per Capita', 12556),
  ('China', 2022, 'GDP per Capita', 12720),
  ('China', 2023, 'GDP per Capita', 13140),
  ('Japan', 2021, 'GDP per Capita', 39301),
  ('Japan', 2022, 'GDP per Capita', 33815),
  ('Japan', 2023, 'GDP per Capita', 34555),
  ('Germany', 2021, 'GDP per Capita', 51238),
  ('Germany', 2022, 'GDP per Capita', 48718),
  ('Germany', 2023, 'GDP per Capita', 52824),
  ('India', 2021, 'GDP per Capita', 2277),
  ('India', 2022, 'GDP per Capita', 2389),
  ('India', 2023, 'GDP per Capita', 2612),
  ('United Kingdom', 2021, 'GDP per Capita', 46510),
  ('United Kingdom', 2022, 'GDP per Capita', 45850),
  ('United Kingdom', 2023, 'GDP per Capita', 48913),
  ('France', 2021, 'GDP per Capita', 43518),
  ('France', 2022, 'GDP per Capita', 42330),
  ('France', 2023, 'GDP per Capita', 44747),
  ('Brazil', 2021, 'GDP per Capita', 7519),
  ('Brazil', 2022, 'GDP per Capita', 8917),
  ('Brazil', 2023, 'GDP per Capita', 9673),
  ('Canada', 2021, 'GDP per Capita', 52078),
  ('Canada', 2022, 'GDP per Capita', 55036),
  ('Canada', 2023, 'GDP per Capita', 53247),
  ('Australia', 2021, 'GDP per Capita', 59934),
  ('Australia', 2022, 'GDP per Capita', 64674),
  ('Australia', 2023, 'GDP per Capita', 63487),
  -- Life Expectancy (years)
  ('United States', 2021, 'Life Expectancy', 77.0),
  ('United States', 2022, 'Life Expectancy', 77.5),
  ('United States', 2023, 'Life Expectancy', 78.0),
  ('China', 2021, 'Life Expectancy', 77.1),
  ('China', 2022, 'Life Expectancy', 77.9),
  ('China', 2023, 'Life Expectancy', 78.2),
  ('Japan', 2021, 'Life Expectancy', 84.5),
  ('Japan', 2022, 'Life Expectancy', 84.7),
  ('Japan', 2023, 'Life Expectancy', 84.9),
  ('Germany', 2021, 'Life Expectancy', 80.6),
  ('Germany', 2022, 'Life Expectancy', 80.8),
  ('Germany', 2023, 'Life Expectancy', 81.0),
  ('India', 2021, 'Life Expectancy', 70.2),
  ('India', 2022, 'Life Expectancy', 70.8),
  ('India', 2023, 'Life Expectancy', 71.5),
  ('United Kingdom', 2021, 'Life Expectancy', 80.7),
  ('United Kingdom', 2022, 'Life Expectancy', 81.0),
  ('United Kingdom', 2023, 'Life Expectancy', 81.2),
  ('France', 2021, 'Life Expectancy', 82.3),
  ('France', 2022, 'Life Expectancy', 82.5),
  ('France', 2023, 'Life Expectancy', 82.7),
  ('Brazil', 2021, 'Life Expectancy', 72.8),
  ('Brazil', 2022, 'Life Expectancy', 73.5),
  ('Brazil', 2023, 'Life Expectancy', 73.9),
  ('Canada', 2021, 'Life Expectancy', 81.7),
  ('Canada', 2022, 'Life Expectancy', 82.0),
  ('Canada', 2023, 'Life Expectancy', 82.2),
  ('Australia', 2021, 'Life Expectancy', 83.3),
  ('Australia', 2022, 'Life Expectancy', 83.5),
  ('Australia', 2023, 'Life Expectancy', 83.7),
  -- HDI Score (×100)
  ('United States', 2021, 'HDI Score', 92.1),
  ('United States', 2022, 'HDI Score', 92.3),
  ('United States', 2023, 'HDI Score', 92.7),
  ('China', 2021, 'HDI Score', 76.8),
  ('China', 2022, 'HDI Score', 77.5),
  ('China', 2023, 'HDI Score', 78.8),
  ('Japan', 2021, 'HDI Score', 92.5),
  ('Japan', 2022, 'HDI Score', 92.7),
  ('Japan', 2023, 'HDI Score', 93.0),
  ('Germany', 2021, 'HDI Score', 94.2),
  ('Germany', 2022, 'HDI Score', 94.3),
  ('Germany', 2023, 'HDI Score', 94.6),
  ('India', 2021, 'HDI Score', 64.5),
  ('India', 2022, 'HDI Score', 65.0),
  ('India', 2023, 'HDI Score', 66.4),
  ('United Kingdom', 2021, 'HDI Score', 92.9),
  ('United Kingdom', 2022, 'HDI Score', 93.0),
  ('United Kingdom', 2023, 'HDI Score', 93.5),
  ('France', 2021, 'HDI Score', 90.3),
  ('France', 2022, 'HDI Score', 90.5),
  ('France', 2023, 'HDI Score', 90.8),
  ('Brazil', 2021, 'HDI Score', 75.4),
  ('Brazil', 2022, 'HDI Score', 76.0),
  ('Brazil', 2023, 'HDI Score', 76.0),
  ('Canada', 2021, 'HDI Score', 93.6),
  ('Canada', 2022, 'HDI Score', 93.7),
  ('Canada', 2023, 'HDI Score', 93.9),
  ('Australia', 2021, 'HDI Score', 95.1),
  ('Australia', 2022, 'HDI Score', 95.1),
  ('Australia', 2023, 'HDI Score', 95.4);
