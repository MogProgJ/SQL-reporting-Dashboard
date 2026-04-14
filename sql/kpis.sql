-- =============================================================
-- Reference KPI queries (used by queries.py at runtime).
-- This file is for documentation / manual testing.
-- =============================================================
-- Total revenue, orders, AOV, unique customers
SELECT COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS total_revenue_cents,
    COUNT(DISTINCT o.id) AS total_orders,
    CASE
        WHEN COUNT(DISTINCT o.id) > 0 THEN SUM(oi.quantity * oi.unit_price_cents) / COUNT(DISTINCT o.id)
        ELSE 0
    END AS avg_order_value_cents,
    COUNT(DISTINCT c.id) AS unique_customers
FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN customers c ON c.id = o.customer_id;
-- Revenue by day
SELECT o.created_at::date AS order_date,
    COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
    COUNT(DISTINCT o.id) AS order_count
FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
GROUP BY o.created_at::date
ORDER BY order_date;
-- Top 10 customers by revenue
SELECT c.name AS customer,
    COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
    COUNT(DISTINCT o.id) AS order_count
FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    JOIN customers c ON c.id = o.customer_id
GROUP BY c.name
ORDER BY revenue_cents DESC
LIMIT 10;
-- Top 10 products by revenue
SELECT p.name AS product,
    COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
    JOIN products p ON p.id = oi.product_id
GROUP BY p.name
ORDER BY revenue_cents DESC
LIMIT 10;
-- Category breakdown
SELECT cat.name AS category,
    COALESCE(SUM(oi.quantity * oi.unit_price_cents), 0) AS revenue_cents,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
    JOIN products p ON p.id = oi.product_id
    JOIN categories cat ON cat.id = p.category_id
GROUP BY cat.name
ORDER BY revenue_cents DESC;
