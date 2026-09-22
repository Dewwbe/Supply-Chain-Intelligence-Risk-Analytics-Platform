# KPI Dictionary

| KPI | Definition | Source tables |
|---|---|---|
| Revenue | Total sales value | `fact_sales.sales_amount` |
| Gross Margin | Revenue − estimated product cost | `fact_sales`, `dim_product.unit_cost` |
| Units Sold | Total quantity sold | `fact_sales.quantity` |
| Inventory Value | Stock × unit cost | `fact_inventory`, `dim_product.unit_cost` |
| Stockout Rate | Stockout days / available days | `fact_inventory` (closing_stock = 0) |
| Fill Rate | Fulfilled demand / total demand | `fact_inventory` |
| Inventory Turnover | COGS / average inventory | `fact_sales`, `fact_inventory` |
| Average Lead Time | Actual delivery − order date | `fact_shipments` |
| Supplier OTD | On-time shipments / total shipments | `fact_shipments` |
| Transport Cost | Total shipment transportation cost | `fact_shipments.transport_cost` |
| Return Rate | Returned units / sold units | `fact_sales` (returns extension) |
| Supplier Risk Score | Weighted composite of OTD, lead-time variability, defect rate, cost volatility, cancellation rate | `src/supplier_risk/scoring.py` |

Every DAX measure in `powerbi/` must trace to a row in this table — no
orphan measures (see `docs/coding_standards.md`).
