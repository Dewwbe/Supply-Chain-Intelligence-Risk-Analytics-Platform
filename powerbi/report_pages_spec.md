# Report Pages — Build Spec

What each of the 5 pages in `GulfMart Supply Chain.Report` shows.
`powerbi/build_report_visuals.py` generates exactly these visuals, so the
report opens fully built; this spec is the reference for what's there and
why. Every visual references a real measure from `_Measures` (see
`powerbi/dax_measures.dax`).

## 1. Executive Overview

| Visual | Fields |
|---|---|
| Card | `_Measures[Total Revenue]` |
| Card | `_Measures[Gross Margin]` |
| Card | `_Measures[Inventory Turnover]` |
| Card | `_Measures[Revenue YoY %]` |
| Line chart | Axis: `dim_date[full_date]` (Year/Month drill). Values: `Total Revenue`, `Total Revenue PY (SPLY)` |
| Clustered bar chart | Axis: `dim_product[category]`. Values: `Revenue % of All Categories` |
| Slicer | `dim_date[year]` |

## 2. Sales & Demand

| Visual | Fields |
|---|---|
| Card | `Total Units Sold`, `Average Order Value`, `Return Rate` |
| Line chart | Axis: `dim_date[full_date]`. Values: `Total Units Sold` |
| Table | Rows: `dim_product[category]`, `dim_product[subcategory]`. Values: `Total Revenue`, `Total Units Sold`, `Average Order Value` |
| Slicer | `dim_location[emirate]` |

## 3. Inventory

| Visual | Fields |
|---|---|
| Card | `Inventory Value`, `Stockout Rate`, `Fill Rate`, `Inventory Turnover` |
| Table | Rows: `dim_product[product_name]`, `dim_warehouse[warehouse_name]`. Values: `Inventory Value`, `Stockout Rate`, `Fill Rate` |
| Bar chart | Axis: `dim_warehouse[warehouse_name]`. Values: `Stockout Rate` — optional manual step, not generated: conditional formatting red above the network average (Format > Bars > Colors > fx) |

## 4. Supplier & Logistics

| Visual | Fields |
|---|---|
| Card | `Average Lead Time`, `Supplier OTD`, `Transport Cost`, `Cancellation Rate` |
| Table | Rows: `dim_supplier[supplier_name]`. Values: `Average Lead Time`, `Lead-Time Std Dev`, `Supplier OTD`, `Cost Variability`, `Supplier Risk Score`, `Supplier Risk Level` |
| Scatter chart | X: `Average Lead Time`. Y: `Supplier Risk Score`. Details: `dim_supplier[supplier_name]` — surfaces suppliers that are both slow *and* risky |
| Bar chart | Axis: `dim_transport[carrier_name]`. Values: `Transport Cost` |

## 5. Scenario Simulator

This page is the one place the report layer does real computation, not
just aggregation — see `docs/kpi_dictionary.md` §7 and
`src/scenario_model/engine.py` for the model this reproduces.

1. **The 3 What-If parameters, as single-value slider slicers.** Each is
   a disconnected `GENERATESERIES` table (created with Desktop's
   **Modeling > New Parameter > Numeric range**); its column has the same
   name as its table:

   | Parameter table / column | Min | Max | Increment |
   |---|---|---|---|
   | Demand Change Parameter | -20 | 30 | 1 |
   | Lead Time Change Parameter | -30 | 50 | 1 |
   | Transport Cost Change Parameter | -20 | 40 | 1 |

   The slicers must stay single-value: the `... Change % Value` measures
   use `SELECTEDVALUE`, which falls back to 0 when a range is selected.
2. **Baseline vs. scenario, side by side** — a table or a pair of card
   groups:

   | Baseline | Scenario |
   |---|---|
   | `Baseline Inventory Value` | `Scenario Projected Inventory Value` |
   | `Baseline Transport Cost` | `Scenario Projected Transport Cost` |
   | `Baseline Stockout Rate` | `Scenario Stockout Rate` |
   | (1 − Baseline Stockout Rate) | `Scenario Fill Rate` |
   | `Baseline Revenue` | `Revenue at Risk` |

3. **KPI cards**: `Scenario Stockout Rate`, `Scenario Fill Rate`,
   `Revenue at Risk` — these are the 3 numbers that move as the sliders
   move; watching them update live is the point of this page.

Sanity check once built: set all 3 sliders to 0 — every "Scenario" value
should exactly equal its "Baseline" counterpart (this is the model's
calibration property, verified in
`tests/unit/test_dax_scenario_formulas.py::test_dax_scenario_stockout_rate_matches_engine[0-0-0]`).
If it doesn't, a slicer is filtering the model instead of feeding a
measure — What-If parameter tables must stay disconnected (no
relationship drawn to any other table).
