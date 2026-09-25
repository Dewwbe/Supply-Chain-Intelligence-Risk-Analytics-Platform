# Report Pages — Build Spec

The 5 pages already exist as empty canvases in `GulfMart Supply Chain.Report`
(correctly named and ordered) once you open the project in Desktop — this
spec is what to place on each one. Every visual references a real measure
from `_Measures` (see `powerbi/dax_measures.dax`); nothing here needs a new
measure invented on the fly. Each page takes roughly 5-10 minutes to build.

Why a spec instead of pre-built visuals: Power BI Desktop isn't installed
in the environment this project was built in, so the report's visual JSON
couldn't be authored and then opened/validated the way the semantic
model's DAX was (see `tests/unit/test_dax_scenario_formulas.py` and
`test_dax_normal_approximations.py` for how *that* was verified). Handing
you unverified visual JSON that might simply fail to open on first launch
would cost you more time than this spec does.

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
| Bar chart | Axis: `dim_warehouse[warehouse_name]`. Values: `Stockout Rate` — conditional formatting: red above the network average (use `Stockout Rate` as the reference line) |

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

1. **Create the 3 What-If parameters, then add them as slicers.** Unlike
   every other table in this model, these are NOT pre-built in the
   TMDL — a hand-authored calculated GENERATESERIES table made Desktop
   refuse to open the whole model ("composite model... entity based
   query sources", see `powerbi/dax_measures.dax`'s comment above
   `Scenario Demand Factor`), so create them here instead:
   **Modeling > New Parameter > Numeric range**, once for each, with
   these exact names/bounds (the measures already reference these exact
   names, so nothing else needs changing once they exist):

   | Parameter table name | Field name | Min | Max | Increment |
   |---|---|---|---|---|
   | Demand Change Parameter | Demand Change % | -20 | 30 | 1 |
   | Lead Time Change Parameter | Lead Time Change % | -30 | 50 | 1 |
   | Transport Cost Change Parameter | Transport Cost Change % | -20 | 40 | 1 |

   Then drop each one's field onto a Slicer visual (single-value slider
   style).
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
