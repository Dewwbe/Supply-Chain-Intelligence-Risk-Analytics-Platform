# Data Dictionary

## Source labeling

This is the single source of truth for the PUBLIC/SYNTHETIC/DERIVED
convention — referenced, not restated, from
[`business_requirements.md`](business_requirements.md) §5 and
[`kpi_dictionary.md`](kpi_dictionary.md).

Every table/column in `data/` and `database/`, and every KPI in
`docs/kpi_dictionary.md`, must be labeled as one of:
- **PUBLIC** — sourced from Olist, DataCo, M5, or UAE Open Data, unmodified
  in meaning (values may be cleaned/standardized, never fabricated).
- **SYNTHETIC** — generated (inventory, purchase orders, warehouses),
  distributions derived from public data, clearly not real GulfMart data.
- **DERIVED** — computed from the above (KPIs, risk scores, forecasts). A
  DERIVED value's presentation-level label is the labels of its inputs
  (e.g. a KPI built from PUBLIC sales and SYNTHETIC unit cost is disclosed
  as PUBLIC + SYNTHETIC, not silently as PUBLIC).

Enforcement: no chart, KPI, or report line may be published without its
label being resolvable from this table or from inline schema comments in
`database/schema/`. SYNTHETIC data is never presented as an observed
GulfMart fact — always framed as modelled/simulated.

## Master data standardization examples

| Source value | Master value |
|---|---|
| `Dubai` / `Dubai Emirate` / `DUBAI` / `DXB` | `Dubai` |
| `Electronics` / `electronic` / `ELECTRONICS` | `Electronics` |

Implemented in `etl/transform/master_data.py` (`standardize_emirate_alias`,
`standardize_order_status`, `standardize_delivery_status`,
`standardize_shipping_mode`, `standardize_category_name`).

## Relabeled PUBLIC data (Phase 2)

Neither Olist (Brazil) nor DataCo (global e-commerce) contains real UAE
geography or real supplier entities. Two fields are therefore a disclosed
**relabeling** of PUBLIC data for narrative context (§5 category
"re-labeled for context"), not an observation about real GulfMart
operations — the raw source value is always kept alongside the relabeled
one for traceability:

| Field | Source | Relabeling rule | Raw value kept in |
|---|---|---|---|
| `dim_location.emirate` | Olist `customer_state`, DataCo `Order Region` | Deterministic weighted hash (SHA-256 of the source string) into one of GulfMart's 5 emirates, weights approximating real population share: Dubai 40% / Abu Dhabi 25% / Sharjah 20% / Ajman 8% / RAK 7%. Same input always yields the same emirate. | `dim_location.region_source` |
| `dim_supplier` (DataCo rows only) | DataCo `Department Name` (11 values) | Each department becomes one supplier, e.g. "Fitness" -> "Fitness Supplier" | `dim_supplier.category` |

`dim_warehouse` (5 rows, one per emirate) is SYNTHETIC by the existing §5
convention (structural necessity for the star schema, not derived from any
source column) — same bucket as `warehouses.csv`, not a new category.

Implementation: `etl/transform/master_data.py:assign_emirate` and
`etl/load/warehouse.py:upsert_dim_supplier`/`upsert_dim_warehouse`.

## Reference tables (`database/seed/`)
`ref_shipping_mode`, `ref_product_category`, `ref_emirate`,
`ref_order_status`, `ref_delivery_status`, `ref_risk_level`, `ref_currency`.
DDL lives in `database/schema/00_reference_tables.sql`; static seed rows in
`database/seed/`, except `ref_product_category`, which is data-driven and
populated by `etl/load/warehouse.py:upsert_ref_product_category` instead.

Full column-level dictionary per fact/dimension table lives alongside the
DDL in `database/schema/01_warehouse_star_schema.sql` (see inline comments)
— duplicated here only at the summary level to avoid drift between two
sources of truth.
