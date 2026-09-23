-- Reference / master-data tables (Phase 2). Each has a unique natural key
-- so warehouse.* tables can FK into it. Seed data lives in database/seed/,
-- except ref_product_category which is data-driven and populated by
-- etl/load/warehouse.py instead of a static seed file.

CREATE SCHEMA IF NOT EXISTS reference;

CREATE TABLE IF NOT EXISTS reference.ref_emirate (
    emirate_code    TEXT PRIMARY KEY,       -- e.g. DXB, AUH, SHJ, AJM, RAK
    emirate_name    TEXT NOT NULL UNIQUE,   -- e.g. Dubai
    is_gulfmart_operating BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS reference.ref_currency (
    currency_code   TEXT PRIMARY KEY,       -- ISO 4217, e.g. AED, USD, BRL
    currency_name   TEXT NOT NULL,
    fx_rate_to_aed  NUMERIC(12, 6) NOT NULL,
    rate_is_fixed_peg BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE only for USD (real AED peg)
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS reference.ref_shipping_mode (
    mode_name       TEXT PRIMARY KEY,       -- e.g. Standard Class, Same Day
    typical_speed_rank SMALLINT NOT NULL    -- 1 = fastest, for sorting in BI
);

CREATE TABLE IF NOT EXISTS reference.ref_order_status (
    status_name     TEXT PRIMARY KEY,       -- canonical, e.g. Delivered
    status_group    TEXT NOT NULL           -- Open | Fulfilled | Cancelled | Exception
);

CREATE TABLE IF NOT EXISTS reference.ref_delivery_status (
    status_name     TEXT PRIMARY KEY,       -- e.g. Shipping On Time
    is_on_time      BOOLEAN                 -- NULL where not applicable (e.g. cancelled)
);

CREATE TABLE IF NOT EXISTS reference.ref_risk_level (
    risk_level      TEXT PRIMARY KEY,       -- Low | Medium | High | Critical
    min_score       NUMERIC(5, 2) NOT NULL,
    max_score       NUMERIC(5, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS reference.ref_product_category (
    category_name   TEXT PRIMARY KEY,       -- standardized, e.g. "Bed Bath Table"
    source_system   TEXT NOT NULL           -- olist | dataco | both
);
