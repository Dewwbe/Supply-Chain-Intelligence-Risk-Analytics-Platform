-- Staging schema (Phase 2): a loose, mostly-TEXT mirror of each raw source,
-- refreshed in full on every ETL run (TRUNCATE + INSERT — see
-- etl/load/staging.py). Not queried by BI; it exists so `transform`/
-- `validate` and any troubleshooting run against a governed table instead
-- of re-reading CSVs, and so raw->staging->warehouse lineage is inspectable.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.olist_orders (
    order_id                        TEXT PRIMARY KEY,
    customer_id                     TEXT,
    order_status                    TEXT,
    order_purchase_timestamp        TIMESTAMP,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.olist_order_items (
    order_id            TEXT NOT NULL,
    order_item_id       INT NOT NULL,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TIMESTAMP,
    price                NUMERIC(12, 2),
    freight_value        NUMERIC(12, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS staging.olist_products (
    product_id              TEXT PRIMARY KEY,
    product_category_name   TEXT,
    product_weight_g        NUMERIC(12, 2),
    product_length_cm       NUMERIC(12, 2),
    product_height_cm       NUMERIC(12, 2),
    product_width_cm        NUMERIC(12, 2)
);

CREATE TABLE IF NOT EXISTS staging.olist_customers (
    customer_id             TEXT PRIMARY KEY,
    customer_unique_id      TEXT,
    customer_zip_code_prefix TEXT,
    customer_city           TEXT,
    customer_state          TEXT
);

CREATE TABLE IF NOT EXISTS staging.dataco_shipments (
    order_id                    TEXT NOT NULL,
    order_item_id               TEXT NOT NULL,
    order_date                  TIMESTAMP,
    shipping_date               TIMESTAMP,
    order_status                TEXT,
    delivery_status              TEXT,
    shipping_mode                TEXT,
    days_for_shipping_real       NUMERIC(6, 2),
    days_for_shipment_scheduled  NUMERIC(6, 2),
    customer_id                  TEXT,
    order_region                 TEXT,
    order_country                TEXT,
    category_name                TEXT,
    department_name              TEXT,
    order_item_quantity           INT,
    sales                          NUMERIC(14, 2),
    order_item_product_price       NUMERIC(14, 2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS staging.uae_trade (
    ref_area        TEXT,
    country         TEXT,
    trade_type      TEXT,
    time_period     TEXT,
    obs_value       NUMERIC(18, 2),
    PRIMARY KEY (country, time_period, trade_type)
);
