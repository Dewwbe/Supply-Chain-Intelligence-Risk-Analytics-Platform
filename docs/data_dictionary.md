# Data Dictionary

## Source labeling
Every table/column in `data/` and `database/` must be labeled as one of:
- **PUBLIC** — sourced from Olist, DataCo, M5, or UAE Open Data, unmodified.
- **SYNTHETIC** — generated (inventory, purchase orders, warehouses),
  distributions derived from public data, clearly not real GulfMart data.
- **DERIVED** — computed from the above (KPIs, risk scores, forecasts).

## Master data standardization examples

| Source value | Master value |
|---|---|
| `Dubai` / `Dubai Emirate` / `DUBAI` / `DXB` | `Dubai` |
| `Electronics` / `electronic` / `ELECTRONICS` | `Electronics` |

## Reference tables (`database/seed/`)
`ref_shipping_mode`, `ref_product_category`, `ref_emirate`,
`ref_order_status`, `ref_delivery_status`, `ref_risk_level`, `ref_currency`.

Full column-level dictionary per fact/dimension table lives alongside the
DDL in `database/schema/01_warehouse_star_schema.sql` (see inline comments)
— duplicated here only at the summary level to avoid drift between two
sources of truth.
