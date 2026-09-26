# KPI Dictionary

Every KPI used anywhere in this project — SQL (`sql/`), Python (`src/`),
Power BI/DAX (`powerbi/`), Excel (`excel/`) or the executive report
(`reports/`) — must be defined here first, with a formula, a grain, an
owning table, and a data-source label. No orphan measures: if a KPI appears
in a dashboard but not in this file, that is a defect, not a stylistic
choice (see [`coding_standards.md`](coding_standards.md)).

Labels (**PUBLIC** / **SYNTHETIC** / **DERIVED**) follow the convention
defined once in [`business_requirements.md`](business_requirements.md) §5
and [`data_dictionary.md`](data_dictionary.md). All KPIs below are
**DERIVED** by definition (they're computed), so the label column instead
states the inputs' labels — that's what actually determines how a KPI may
be presented in the executive report.

Owning tables reference `warehouse.*` as defined in
[`database/schema/01_warehouse_star_schema.sql`](../database/schema/01_warehouse_star_schema.sql).
Tables marked **(planned, Phase 3)** don't exist yet — they are named here
so the Phase 3 schema is built to serve these KPIs, not the other way
around.

---

## 1. Sales / Revenue

| KPI | Formula | Grain | Owning table(s) | Inputs' label | Stakeholders | BI page |
|---|---|---|---|---|---|---|
| Total Revenue | `SUM(sales_amount)` | any (date/product/location/customer) | `fact_sales.sales_amount` | PUBLIC (Olist) | COO, Finance | Executive Overview |
| Total Units Sold | `SUM(quantity)` | any | `fact_sales.quantity` | PUBLIC | COO | Sales & Demand |
| Gross Margin | `SUM(sales_amount) − SUM(quantity * unit_cost)` | any | `fact_sales`, `dim_product.unit_cost` | PUBLIC + SYNTHETIC (`unit_cost` is modelled, not observed in Olist) | COO, Finance | Executive Overview |
| Average Order Value (AOV) | `SUM(sales_amount) / COUNT(DISTINCT order_id)` | date/location/customer segment | `fact_sales.sales_amount`, `fact_sales.order_id` | PUBLIC | COO | Sales & Demand |
| Return Rate | `SUM(returned_quantity) / SUM(quantity)` | product/date | `fact_returns` **(planned, Phase 3)** | PUBLIC (Olist review/return signal) | COO, Finance | Sales & Demand |

## 2. Inventory

| KPI | Formula | Grain | Owning table(s) | Inputs' label | Stakeholders | BI page |
|---|---|---|---|---|---|---|
| Inventory Value | `SUM(closing_stock * unit_cost)` | date/product/warehouse | `fact_inventory.closing_stock`, `dim_product.unit_cost` | SYNTHETIC (inventory) + SYNTHETIC (unit_cost) | Finance, Supply Chain Manager | Inventory |
| Stockout Rate | `COUNT(days WHERE closing_stock = 0) / COUNT(available_days)` | product/warehouse/period | `fact_inventory.closing_stock` | SYNTHETIC | Supply Chain Manager, COO | Inventory |
| Fill Rate | `1 − (unmet_demand / total_demand)`, where `unmet_demand = GREATEST(sold_quantity_requested − sold_quantity_fulfilled, 0)` | product/warehouse/period | `fact_inventory` | SYNTHETIC | Supply Chain Manager, COO | Inventory |
| Inventory Turnover | `COGS / average_inventory_value`, `COGS = SUM(quantity * unit_cost)` (sales side), `average_inventory_value = AVG(opening_stock, closing_stock) * unit_cost` | product/warehouse/period | `fact_sales`, `fact_inventory`, `dim_product.unit_cost` | PUBLIC + SYNTHETIC | COO, Finance | Executive Overview, Inventory |

## 3. Supplier / Logistics

| KPI | Formula | Grain | Owning table(s) | Inputs' label | Stakeholders | BI page |
|---|---|---|---|---|---|---|
| Average Lead Time | `AVG(actual_delivery_date − order_date)` | supplier/product/period | `fact_shipments.order_date_key`, `actual_delivery_date_key` | PUBLIC (DataCo) | Procurement, Supply Chain Manager | Supplier & Logistics |
| Lead-Time Std Dev | `STDDEV(actual_delivery_date − order_date)` | supplier | `fact_shipments` | PUBLIC | Procurement | Supplier & Logistics |
| Supplier OTD (On-Time Delivery) | `COUNT(actual_delivery_date_key <= expected_delivery_date_key) / COUNT(shipments)` | supplier/period | `fact_shipments` | PUBLIC | Procurement, COO | Supplier & Logistics |
| Transport Cost | `SUM(transport_cost)` | shipment/supplier/mode/period | `fact_shipments.transport_cost` | PUBLIC | Finance, COO | Supplier & Logistics |
| Cancellation Rate | `COUNT(cancelled_orders) / COUNT(total_orders)` | supplier/period | `fact_purchase_orders` **(planned, Phase 3)** | SYNTHETIC | Procurement | Supplier & Logistics |
| Cost Variability | `STDDEV(unit_cost) / AVG(unit_cost)` per supplier | supplier | `fact_purchase_orders` **(planned, Phase 3)** | SYNTHETIC | Procurement, Finance | Supplier & Logistics |

## 4. Supplier Risk (Phase 7)

| KPI | Formula | Grain | Owning table(s) | Inputs' label | Stakeholders | BI page |
|---|---|---|---|---|---|---|
| Supplier Risk Score (0–100) | Weighted, normalized composite: `w1*(1−OTD) + w2*norm(avg_lead_time) + w3*norm(lead_time_std/avg_lead_time) + w4*defect_rate + w5*cost_variability + w6*cancellation_rate`; weights documented in `src/supplier_risk/scoring.py` (`DEFAULT_WEIGHTS`) | supplier | `fact_shipments`, `fact_purchase_orders`, `fact_returns`, `src/supplier_risk/scoring.py` | DERIVED from PUBLIC + SYNTHETIC | Procurement, COO | Supplier & Logistics |
| Supplier Risk Level | `CASE score WHEN <25 THEN 'Low' WHEN <50 THEN 'Medium' WHEN <75 THEN 'High' ELSE 'Critical'` (thresholds documented, not implied) | supplier | same as above | DERIVED | Procurement, COO | Supplier & Logistics |

## 5. Forecast Accuracy (Phase 6 — model comparison, not a dashboard KPI)

| Metric | Formula | Used for |
|---|---|---|
| MAE | `mean(|actual − forecast|)` | Model comparison table |
| RMSE | `sqrt(mean((actual − forecast)^2))` | Model comparison table |
| MAPE | `mean(|actual − forecast| / actual) * 100` | Model comparison table (unstable near zero demand — reported alongside WAPE) |
| WAPE | `sum(|actual − forecast|) / sum(actual) * 100` | Preferred headline metric for low-volume SKUs |

No model may be called "best" until all four are reported for all four
candidate models (Seasonal Naive, ETS, SARIMA, XGBoost) on the same
time-based test split — per `implementation_plan.md`.

## 6. Anomaly Detection (Phase 8 — flags, not aggregate KPIs)

| Field | Meaning |
|---|---|
| `anomaly_score` | Method-specific score (IQR distance, Z-score, or Isolation Forest score) |
| `severity` | Derived bucket (Low/Medium/High) from `anomaly_score`, thresholds documented in `src/anomaly_detection/` |

Anomalies are computed over: daily sales, inventory changes, shipment
delays, transport costs, supplier lead times — see PRD Phase 8 for the
full output schema (`anomaly_id`, `date`, `entity`, `metric`,
`expected_value`, `actual_value`, `anomaly_score`, `severity`).

## 7. Scenario Analysis (Phase 9 — What-If)

| KPI | Formula | Grain | Owning table(s) | Inputs' label | Stakeholders | BI page |
|---|---|---|---|---|---|---|
| Revenue at Risk | `projected_revenue * stockout_rate`, where `projected_revenue = Total Revenue * (1 + demand_change_pct/100)` | scenario run | `src/scenario_model/engine.py` | DERIVED from PUBLIC + SYNTHETIC | COO, Finance | Scenario Simulator |

Projected Inventory, Projected Transport Cost, Stockout Rate and Fill Rate
on the Scenario Simulator page are **not new KPIs** — they are Inventory
Value (§2), Transport Cost (§3), Stockout Rate (§2) and Fill Rate (§2)
evaluated at a "what-if" grain (baseline × the 3 scenario parameters:
demand change, lead-time change, transport-cost change) instead of the
"actual" grain, per `src/scenario_model/engine.py`'s calibrated model. Only
Revenue at Risk is genuinely new, since no "actual" equivalent exists
elsewhere — it is introduced here, not left as an orphan measure in the
Power BI/Excel scenario layer.

---

## Traceability check

Every KPI above must map back to at least one stakeholder need in
[`business_requirements.md`](business_requirements.md) §3 and at least one
Power BI page planned for Phase 10. If a future KPI is proposed that
doesn't satisfy both, it does not belong in this file (or in the
dashboards).
