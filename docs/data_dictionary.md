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

## Reference tables (`database/seed/`)
`ref_shipping_mode`, `ref_product_category`, `ref_emirate`,
`ref_order_status`, `ref_delivery_status`, `ref_risk_level`, `ref_currency`.

Full column-level dictionary per fact/dimension table lives alongside the
DDL in `database/schema/01_warehouse_star_schema.sql` (see inline comments)
— duplicated here only at the summary level to avoid drift between two
sources of truth.
