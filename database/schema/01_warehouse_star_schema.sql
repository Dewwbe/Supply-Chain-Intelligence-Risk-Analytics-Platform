-- Star schema: warehouse layer
-- Naming: dim_* for dimensions, fact_* for facts. Surrogate keys are
-- BIGINT identity columns; natural/source keys are kept as *_source_id.

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key        INT PRIMARY KEY,        -- YYYYMMDD
    full_date       DATE NOT NULL,
    day_of_week     SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    year            SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    is_uae_holiday  BOOLEAN NOT NULL DEFAULT FALSE,
    season_label    TEXT                     -- Ramadan, Eid, Summer, Back-to-school, National Day, Year-end
);

CREATE TABLE IF NOT EXISTS warehouse.dim_location (
    location_key    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    emirate         TEXT NOT NULL,           -- Dubai, Abu Dhabi, Sharjah, Ajman, RAK, Fujairah, UAQ
    city            TEXT,
    region_source   TEXT                     -- raw source value, pre master-data standardization
);

CREATE TABLE IF NOT EXISTS warehouse.dim_product (
    product_key     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_source_id TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,           -- standardized via master data rules
    subcategory     TEXT,
    brand           TEXT,
    unit_cost       NUMERIC(12, 2),
    unit_price      NUMERIC(12, 2),
    supplier_key    BIGINT
);

CREATE TABLE IF NOT EXISTS warehouse.dim_supplier (
    supplier_key    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_source_id TEXT NOT NULL,
    supplier_name   TEXT NOT NULL,
    country         TEXT,
    category        TEXT,
    standard_lead_time_days INT
);

CREATE TABLE IF NOT EXISTS warehouse.dim_warehouse (
    warehouse_key   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_source_id TEXT NOT NULL,
    warehouse_name  TEXT NOT NULL,
    location_key    BIGINT REFERENCES warehouse.dim_location(location_key),
    capacity_units  INT
);

CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_key    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_source_id TEXT NOT NULL,
    customer_segment TEXT,
    location_key    BIGINT REFERENCES warehouse.dim_location(location_key),
    signup_date_key INT REFERENCES warehouse.dim_date(date_key)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_sales (
    sales_key       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id        TEXT NOT NULL,
    date_key        INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    product_key     BIGINT NOT NULL REFERENCES warehouse.dim_product(product_key),
    customer_key    BIGINT REFERENCES warehouse.dim_customer(customer_key),
    location_key    BIGINT REFERENCES warehouse.dim_location(location_key),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    discount        NUMERIC(12, 2) DEFAULT 0 CHECK (discount >= 0),
    sales_amount    NUMERIC(14, 2) NOT NULL CHECK (sales_amount >= 0)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_inventory (
    inventory_key   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key        INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    product_key     BIGINT NOT NULL REFERENCES warehouse.dim_product(product_key),
    warehouse_key   BIGINT NOT NULL REFERENCES warehouse.dim_warehouse(warehouse_key),
    opening_stock   INT NOT NULL CHECK (opening_stock >= 0),
    received_quantity INT NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    sold_quantity   INT NOT NULL DEFAULT 0 CHECK (sold_quantity >= 0),
    closing_stock   INT NOT NULL CHECK (closing_stock >= 0)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_shipments (
    shipment_key    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shipment_source_id TEXT NOT NULL,
    supplier_key    BIGINT NOT NULL REFERENCES warehouse.dim_supplier(supplier_key),
    warehouse_key   BIGINT NOT NULL REFERENCES warehouse.dim_warehouse(warehouse_key),
    product_key     BIGINT NOT NULL REFERENCES warehouse.dim_product(product_key),
    order_date_key  INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    expected_delivery_date_key INT REFERENCES warehouse.dim_date(date_key),
    actual_delivery_date_key   INT REFERENCES warehouse.dim_date(date_key),
    quantity        INT NOT NULL CHECK (quantity > 0),
    transport_mode  TEXT,
    transport_cost  NUMERIC(12, 2) CHECK (transport_cost >= 0),
    CHECK (
        actual_delivery_date_key IS NULL
        OR expected_delivery_date_key IS NULL
        OR actual_delivery_date_key >= order_date_key
    )
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON warehouse.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_inventory_date ON warehouse.fact_inventory(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_shipments_supplier ON warehouse.fact_shipments(supplier_key);
