# Database Schema

All monetary values are stored in **cents** to avoid floating-point rounding issues.

## customers

| Column   | Type      | Constraints             |
|----------|-----------|-------------------------|
| id       | BIGSERIAL | PRIMARY KEY             |
| name     | TEXT      | NOT NULL                |
| segment  | TEXT      | NOT NULL, DEFAULT 'Standard' |
| city     | TEXT      | NOT NULL, DEFAULT 'Unknown'  |

## categories

| Column | Type      | Constraints        |
|--------|-----------|--------------------|
| id     | BIGSERIAL | PRIMARY KEY        |
| name   | TEXT      | NOT NULL, UNIQUE   |

## products

| Column           | Type      | Constraints                          |
|------------------|-----------|--------------------------------------|
| id               | BIGSERIAL | PRIMARY KEY                          |
| name             | TEXT      | NOT NULL                             |
| category_id      | BIGINT    | NOT NULL, FK → categories(id)        |
| unit_price_cents | INTEGER   | NOT NULL, CHECK (unit_price_cents > 0) |

## orders

| Column      | Type        | Constraints                     |
|-------------|-------------|---------------------------------|
| id          | BIGSERIAL   | PRIMARY KEY                     |
| customer_id | BIGINT      | NOT NULL, FK → customers(id)    |
| status      | TEXT        | NOT NULL, DEFAULT 'completed'   |
| created_at  | TIMESTAMPTZ | NOT NULL, DEFAULT now()         |

## order_items

| Column           | Type      | Constraints                          |
|------------------|-----------|--------------------------------------|
| id               | BIGSERIAL | PRIMARY KEY                          |
| order_id         | BIGINT    | NOT NULL, FK → orders(id)            |
| product_id       | BIGINT    | NOT NULL, FK → products(id)          |
| quantity         | INTEGER   | NOT NULL, CHECK (quantity > 0)       |
| unit_price_cents | INTEGER   | NOT NULL, CHECK (unit_price_cents > 0) |

## Relationships

```
customers  1──∞  orders
orders     1──∞  order_items
products   1──∞  order_items
categories 1──∞  products
```

This schema supports: top products, category mix, customer revenue, order trends, and average order value reporting.
