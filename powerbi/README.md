# Power BI

`GulfMart Supply Chain.pbip` — a Power BI Project (TMDL semantic model +
PBIR report), not a `.pbix` (the `.pbix` a user saves from opening this is
gitignored — see `.gitignore` — same convention as everywhere else in this
repo: the reproducible source is committed, the compiled binary isn't).

**Built without Power BI Desktop installed**, then debugged live against a
real Desktop install through several rounds of "Copy details to clipboard"
error output. Two changes came out of that process, both load-bearing:

- **Sourced from CSV extracts (`powerbi/data/*.csv`), not a live Postgres
  connection.** A `PostgreSQL.Database(...)` connector made Desktop refuse
  the whole model with *"A composite model cannot be used with entity
  based query sources"* — confirmed, after switching the M query itself
  to `Value.NativeQuery` and separately removing every calculated table
  from the model (two different fix attempts, each addressing a different
  plausible cause), that the live connector was the trigger regardless of
  query style or the presence of calculated tables.
  `supplier_risk_scores`, already CSV-sourced from the start, never hit
  this error across any of those attempts — that's the evidence the
  file-based approach works. Run `python powerbi/export_csv_extracts.py`
  (after `make etl`, or whenever the warehouse changes) to regenerate the
  CSVs, then **Refresh** in Desktop.
- **The 3 What-If parameters (Scenario Simulator page) are not pre-built
  in the TMDL.** A hand-authored calculated `GENERATESERIES` table was
  the original, wrong theory for the "composite model" error above (fixed
  before discovering the connector was the real cause) — removed anyway,
  since Desktop's own **Modeling > New Parameter** wizard builds the
  identical structure in a few clicks and doesn't carry that risk. See
  step 5 below for the exact names/bounds; the measures already reference
  them by name, so nothing else needs to change once they exist.

## Setup

1. `python powerbi/export_csv_extracts.py` — requires the Postgres
   container running (`docker compose up -d postgres`). Exports via
   `docker exec ... psql \copy`, not a network connection to whatever
   host port is mapped — on the dev machine this was built on, a native
   Windows `postgres.exe` service was *also* listening on port 5432,
   silently intercepting connections meant for the container (`docker ps`
   showed the container healthy and correctly credentialed; connections
   via the host port still failed auth). Going through the container
   directly sidesteps that regardless of what's bound to the host port.
2. Open `GulfMart Supply Chain.pbip` in Power BI Desktop (2024+, TMDL/PBIP
   project support is GA).
3. **Transform Data > Manage Parameters**: set `RepoRoot` to this
   checkout's path (it feeds every table's CSV path, e.g.
   `E:\...\Supply-Chain-Intelligence-Risk-Analytics-Platform\`).
4. **Home > Refresh** to load all 13 tables from the CSVs.
5. Table view > `dim_date` > **Mark as Date Table** (Date Column =
   `full_date`) — required for `DATEADD`/`SAMEPERIODLASTYEAR`.
6. **Modeling > New Parameter > Numeric range**, once for each:

   | Parameter table name | Field name | Min | Max | Increment |
   |---|---|---|---|---|
   | Demand Change Parameter | Demand Change % | -20 | 30 | 1 |
   | Lead Time Change Parameter | Lead Time Change % | -30 | 50 | 1 |
   | Transport Cost Change Parameter | Transport Cost Change % | -20 | 40 | 1 |

7. The 5 report pages (Executive Overview, Sales & Demand, Inventory,
   Supplier & Logistics, Scenario Simulator) exist as empty, correctly
   named/ordered canvases — build each one from
   [`report_pages_spec.md`](report_pages_spec.md) (visual-by-visual, ~5-10
   min/page). Visual JSON wasn't hand-authored: no Desktop was available
   while building this to validate it, and broken visual JSON on first
   open would have cost more time than the spec does — unlike the
   semantic model issues above, which *were* worth debugging live since
   the model is the part every page depends on.

## Measures

Every measure lives in `_Measures` (see [`dax_measures.dax`](dax_measures.dax)
for the human-readable source; the same expressions are embedded in
`GulfMart Supply Chain.SemanticModel/definition/tables/_Measures.tmdl`)
and traces to a row in `docs/kpi_dictionary.md` — no orphan measures.

The two normal-distribution approximations the Scenario Simulator
measures need (DAX has neither `NORM.S.DIST` nor `NORM.S.INV`) are
verified against `scipy.stats.norm` and against
`src/scenario_model/engine.py`'s actual output in
`tests/unit/test_dax_normal_approximations.py` and
`tests/unit/test_dax_scenario_formulas.py` — that verification doesn't
need Desktop and was done independently of the live debugging above.
