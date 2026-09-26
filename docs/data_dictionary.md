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

## SYNTHETIC data (Phase 3)

`dim_store`, `dim_transport`, `fact_purchase_orders`, `fact_returns`, and
`fact_inventory` have no equivalent at all in Olist/DataCo (no physical
stores, no PO history, no returns, no stock levels). Each is simulated
from distributions derived from the real data — never a fabricated
constant — and implemented in `etl/synthesize/`:

| Table / column | Derived from | Method |
|---|---|---|
| `dim_product.unit_cost` | real `unit_price` | category margin rate in [15%, 45%], `etl/synthesize/product_cost.py` |
| `dim_supplier.standard_lead_time_days` | — | deterministic per supplier, [3, 21] days, `etl/synthesize/supplier_terms.py` |
| `dim_store` / `fact_sales.store_key` | — | 1 Online + 8 physical stores across the 5 emirates; each sale assigned ~75% Online / 25% to a physical store in its own (already-relabeled) emirate, `etl/synthesize/stores.py` |
| `dim_transport` / `fact_shipments.transport_key`, `transport_cost` | real `Shipping Mode`, a modeled intra-UAE distance | 2 fictional carriers (not real logistics companies) x the 4 real shipping modes; cost = distance x carrier's AED/km, `etl/synthesize/transport.py` |
| `fact_purchase_orders` | real per-product sales velocity (from `fact_sales`) | order frequency/size scaled to how much of that product actually sold; lead time from `dim_supplier`; ~5% modeled cancellation rate, `etl/synthesize/purchase_orders.py` |
| `fact_returns` | real `fact_sales` rows | per-category return rate in [2%, 12%] sampled against real sales lines — the sale is real, whether it was "returned" is synthetic, `etl/synthesize/returns.py` |
| `fact_inventory` | real daily `fact_sales` quantity, top 500 products by volume | (s, S) reorder-point simulation per product's one assigned primary warehouse; `sold_quantity` is real, stock levels are simulated, `etl/synthesize/inventory.py`. Scoped to the top 500 products by quantity — not all ~33k — since long-tail SKUs with a handful of lifetime sales don't produce meaningful stockout/turnover analytics; a stated scope limit, not a silent drop. |

Every value here is a deterministic function of a real key (`etl/synthesize/rng.py`), so re-running the pipeline reproduces identical synthetic data — nothing here uses `random`.

## UAE contextual layer (Phase 5)

`reference.ref_emirate` now lists all 7 real UAE emirates (Dubai, Abu Dhabi,
Sharjah, Ajman, Ras Al Khaimah, Fujairah, Umm Al Quwain) for geographic
reference completeness — `is_gulfmart_operating` still marks only the 5
GulfMart actually operates in (`docs/business_requirements.md` §1)
unchanged. The synthetic emirate assignment (`etl/transform/master_data.py`)
still only ever picks from those 5, so `dim_location`/`fact_sales` will
never show Fujairah/Umm Al Quwain rows in practice — adding the other 2 to
the reference table doesn't change what data GulfMart is modeled as having.

`warehouse.dim_date.is_uae_holiday`/`season_label` (left `False`/`NULL` in
Phase 2 pending a real calendar) are now populated from
`src/common/uae_calendar.py`, which draws a hard line between two kinds of
"season":

| Kind | Categories | Basis |
|---|---|---|
| Real, published dates | Ramadan, Eid al-Fitr, Eid al-Adha, National Day | Commonly cited Gregorian equivalents of the Islamic lunar calendar (2015-2018, the years Olist+DataCo span) / the fixed December 2, 1971 civil date — a calendrical fact, not fabricated data |
| Stated, disclosed windows | Summer, Back-to-school, Year-end | Declared month/day ranges (e.g. "Summer = June 1 - September 15"), not discovered from the data — a different definition would give different test results, which is exactly why these are *tested*, never assumed, in `notebooks/02_sales_eda.ipynb` §4 |

Only Eid (both) and National Day set `is_uae_holiday` — Ramadan itself
isn't a UAE public holiday (shortened hours, not a closure), so it only
ever sets `season_label`.

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
