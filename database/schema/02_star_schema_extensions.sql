-- Phase 3 star-schema extensions. Additive only — no Phase 2 column is
-- removed or retyped. New facts/dimensions are SYNTHETIC (simulated from
-- distributions derived from real data, never real observations) — see
-- docs/data_dictionary.md "Relabeled/synthesized PUBLIC data (Phase 3)".

CREATE TABLE IF NOT EXISTS warehouse.dim_store (
    store_key       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_source_id TEXT NOT NULL UNIQUE,
    store_name      TEXT NOT NULL,
    store_type      TEXT NOT NULL CHECK (store_type IN ('Online', 'Physical')),
    location_key    BIGINT REFERENCES warehouse.dim_location(location_key)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_transport (
    transport_key   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transport_source_id TEXT NOT NULL UNIQUE,
    mode_name       TEXT NOT NULL REFERENCES reference.ref_shipping_mode(mode_name),
    carrier_name    TEXT NOT NULL,
    vehicle_type    TEXT,
    avg_cost_per_km NUMERIC(10, 2) NOT NULL CHECK (avg_cost_per_km >= 0)
);

ALTER TABLE warehouse.fact_sales
    ADD COLUMN IF NOT EXISTS store_key BIGINT REFERENCES warehouse.dim_store(store_key);

ALTER TABLE warehouse.fact_shipments
    ADD COLUMN IF NOT EXISTS transport_key BIGINT REFERENCES warehouse.dim_transport(transport_key);

CREATE TABLE IF NOT EXISTS warehouse.fact_purchase_orders (
    po_key          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    po_source_id    TEXT NOT NULL UNIQUE,
    supplier_key    BIGINT NOT NULL REFERENCES warehouse.dim_supplier(supplier_key),
    warehouse_key   BIGINT NOT NULL REFERENCES warehouse.dim_warehouse(warehouse_key),
    product_key     BIGINT NOT NULL REFERENCES warehouse.dim_product(product_key),
    order_date_key  INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    expected_delivery_date_key INT REFERENCES warehouse.dim_date(date_key),
    actual_delivery_date_key   INT REFERENCES warehouse.dim_date(date_key),
    order_status    TEXT REFERENCES reference.ref_order_status(status_name),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_cost       NUMERIC(12, 2) NOT NULL CHECK (unit_cost >= 0),
    total_cost      NUMERIC(14, 2) NOT NULL CHECK (total_cost >= 0)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_returns (
    return_key      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sales_key       BIGINT NOT NULL UNIQUE REFERENCES warehouse.fact_sales(sales_key),
    return_date_key INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    reason          TEXT NOT NULL,
    returned_quantity INT NOT NULL CHECK (returned_quantity > 0),
    refund_amount   NUMERIC(14, 2) NOT NULL CHECK (refund_amount >= 0)
);

-- fact_inventory was created (empty) in Phase 2 without a natural-key
-- constraint since nothing populated it yet; added now so Phase 3's
-- simulator (etl/synthesize/inventory.py) can upsert by (product, warehouse, date).
CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_inventory_product_warehouse_date
    ON warehouse.fact_inventory(product_key, warehouse_key, date_key);

CREATE INDEX IF NOT EXISTS idx_fact_purchase_orders_supplier ON warehouse.fact_purchase_orders(supplier_key);
CREATE INDEX IF NOT EXISTS idx_fact_purchase_orders_date ON warehouse.fact_purchase_orders(order_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_returns_date ON warehouse.fact_returns(return_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_store ON warehouse.fact_sales(store_key);
CREATE INDEX IF NOT EXISTS idx_fact_shipments_transport ON warehouse.fact_shipments(transport_key);
