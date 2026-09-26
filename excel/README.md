# Excel

Two workbooks, both built by driving a real Excel process via COM
(`pywin32`) — not written as static files — so PivotTables are genuine
native pivot objects and every value is Excel's own calculation engine,
not a pre-baked number. Neither `.xlsx` is committed (see `.gitignore`);
the build scripts are the reproducible source, same convention as every
other generated artifact in this repo (notebooks, reports/).

## `kpi_validation.xlsx` — `build_kpi_validation.py`

Independently re-derives the same 10 headline KPIs as
[`src/kpi/summary.py`](../src/kpi/summary.py) (also the ground truth
behind [`powerbi/dax_measures.dax`](../powerbi/dax_measures.dax)), using
`SUMIFS`/`COUNTIFS`/`XLOOKUP` formulas over a raw warehouse extract
(~655k rows across 3 data sheets), plus 2 native PivotTables. The
`KPI Validation` sheet compares its own Excel-computed value against a
snapshot of `src/kpi/summary.py`'s output for every KPI and flags
`MATCH`/`CHECK` with conditional formatting.

**Verified, not assumed**: running the script prints a live comparison
(all 10 currently `MATCH`, confirmed by reopening the saved file and
reading the values back). `XLOOKUP` is wrapped in `IFERROR(...,
INDEX/MATCH)` — this project's Excel build (perpetual-license 16.0, not a
Microsoft 365 subscription) doesn't have `XLOOKUP` at all, confirmed by a
live `#NAME?` test, so the formula falls back to `INDEX`/`MATCH` there
while still using native `XLOOKUP` on a newer Excel.

Run: `python excel/build_kpi_validation.py` (Windows, Excel installed,
`DATABASE_URL` pointing at the populated warehouse). Regenerate after
`make etl`.

## `scenario_analysis.xlsx` — `build_scenario_analysis.py`

Mirrors `POST /api/v1/scenario/simulate`
([`src/scenario_model/engine.py`](../src/scenario_model/engine.py))
exactly, using `NORM.S.INV`/`NORM.DIST` natively — Excel has both, unlike
DAX (see `powerbi/dax_measures.dax`'s comments on why the Power BI version
needed a rational approximation instead). 3 input cells (data-validated to
the same bounds as `ScenarioRequest`) drive the same calibrated
safety-stock model, with baseline vs. scenario shown side by side.

**Verified end-to-end, automatically**: the build script sets those 3
input cells to each of the same 9 representative scenarios used in
`notebooks/09_scenario_analysis.ipynb`, forces recalculation, and diffs
Excel's computed `stockout_rate`/`fill_rate`/`projected_inventory_aed`/
`projected_transport_cost_aed`/`revenue_at_risk_aed` against
`run_scenario()`'s Python output for the same inputs — all 9 matched
(tolerance accounts for `engine.py` rounding its output to 2-4 decimals,
which this workbook deliberately doesn't). The script exits non-zero if
any scenario doesn't match, so a future formula edit that breaks parity
fails loudly, not silently.

Run: `python excel/build_scenario_analysis.py` (same prerequisites as
above).
