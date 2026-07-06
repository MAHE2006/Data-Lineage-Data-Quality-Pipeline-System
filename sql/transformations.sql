-- ============================================================
-- transformations.sql
-- SQL transformation layer for the Data Lineage & Data Quality
-- Pipeline. Runs against SQLite (loaded by 03_transform.py) but
-- uses standard ANSI SQL that ports to Postgres/MySQL/SQL Server
-- with minimal changes.
--
-- Builds a small star schema from the cleaned "validated_orders"
-- table:
--     dim_customer, dim_product, dim_date  -> fact_orders
-- then reporting views used for the Power BI dashboard.
-- ============================================================

-- 1) DIMENSION: Customers
DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer AS
SELECT
    customer_id,
    customer_email,
    COUNT(DISTINCT order_id)   AS lifetime_orders,
    ROUND(SUM(total_amount),2) AS lifetime_spend
FROM validated_orders
GROUP BY customer_id, customer_email;

-- 2) DIMENSION: Products
DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product AS
SELECT
    product_id,
    product_category,
    ROUND(AVG(unit_price), 2) AS avg_unit_price,
    COUNT(*)                  AS times_ordered
FROM validated_orders
GROUP BY product_id, product_category;

-- 3) DIMENSION: Date (simple calendar dimension derived from order_date)
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date AS
SELECT DISTINCT
    order_date,
    CAST(strftime('%Y', order_date) AS INTEGER) AS order_year,
    CAST(strftime('%m', order_date) AS INTEGER) AS order_month,
    CAST(strftime('%d', order_date) AS INTEGER) AS order_day,
    CASE CAST(strftime('%m', order_date) AS INTEGER)
        WHEN 1 THEN 'Q1' WHEN 2 THEN 'Q1' WHEN 3 THEN 'Q1'
        WHEN 4 THEN 'Q2' WHEN 5 THEN 'Q2' WHEN 6 THEN 'Q2'
        WHEN 7 THEN 'Q3' WHEN 8 THEN 'Q3' WHEN 9 THEN 'Q3'
        ELSE 'Q4'
    END AS order_quarter
FROM validated_orders;

-- 4) FACT TABLE: Orders (grain = one row per order line)
DROP TABLE IF EXISTS fact_orders;
CREATE TABLE fact_orders AS
SELECT
    o.order_id,
    o.customer_id,
    o.product_id,
    o.order_date,
    o.region,
    o.payment_method,
    o.quantity,
    o.unit_price,
    o.total_amount
FROM validated_orders o;

-- ============================================================
-- REPORTING VIEWS (feed Power BI / BI dashboards directly)
-- ============================================================

-- Monthly revenue trend
DROP VIEW IF EXISTS vw_monthly_revenue;
CREATE VIEW vw_monthly_revenue AS
SELECT
    d.order_year,
    d.order_month,
    ROUND(SUM(f.total_amount), 2) AS total_revenue,
    COUNT(DISTINCT f.order_id)    AS total_orders
FROM fact_orders f
JOIN dim_date d ON f.order_date = d.order_date
GROUP BY d.order_year, d.order_month
ORDER BY d.order_year, d.order_month;

-- Revenue and order count by product category
DROP VIEW IF EXISTS vw_category_performance;
CREATE VIEW vw_category_performance AS
SELECT
    p.product_category,
    COUNT(f.order_id)             AS orders,
    SUM(f.quantity)                AS units_sold,
    ROUND(SUM(f.total_amount), 2)  AS revenue
FROM fact_orders f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.product_category
ORDER BY revenue DESC;

-- Revenue by region
DROP VIEW IF EXISTS vw_region_performance;
CREATE VIEW vw_region_performance AS
SELECT
    region,
    COUNT(order_id)            AS orders,
    ROUND(SUM(total_amount),2) AS revenue
FROM fact_orders
GROUP BY region
ORDER BY revenue DESC;

-- Top 10 customers by spend
DROP VIEW IF EXISTS vw_top_customers;
CREATE VIEW vw_top_customers AS
SELECT customer_id, customer_email, lifetime_orders, lifetime_spend
FROM dim_customer
ORDER BY lifetime_spend DESC
LIMIT 10;

-- Anomaly view: orders where total_amount doesn't match quantity*unit_price
-- (safety-net check even after cleaning — should return 0 rows)
DROP VIEW IF EXISTS vw_anomalies_amount_mismatch;
CREATE VIEW vw_anomalies_amount_mismatch AS
SELECT *
FROM fact_orders
WHERE ROUND(quantity * unit_price, 2) <> ROUND(total_amount, 2);

-- Anomaly view: single-order spend outliers (>3x the average order value)
DROP VIEW IF EXISTS vw_anomalies_high_value_orders;
CREATE VIEW vw_anomalies_high_value_orders AS
SELECT *
FROM fact_orders
WHERE total_amount > (SELECT AVG(total_amount) * 3 FROM fact_orders)
ORDER BY total_amount DESC;
