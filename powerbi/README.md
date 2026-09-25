# Power BI

`GulfMart Supply Chain.pbip` — a Power BI Project (TMDL semantic model +
PBIR report), not a `.pbix` (the `.pbix` a user saves from opening this is
gitignored — see `.gitignore` — same convention as everywhere else in this
repo: the reproducible source is committed, the compiled binary isn't).

**Built without Power BI Desktop installed** (not available in the
environment this project was developed in), so open it expecting some
first-open friction:

1. Open `GulfMart Supply Chain.pbip` in Power BI Desktop (2024+, TMDL/PBIP
   project support is GA).
2. When prompted for the Postgres connection, the `PGServer`/`PGDatabase`
   M parameters (Transform Data > Manage Parameters) default to
   `localhost:5434` / `gulfmart_analytics` — check these against your own
   `docker-compose` port mapping (see the root README) before refreshing;
   `RepoRoot` similarly needs to point at your checkout for
   `supplier_risk_scores` (CSV-sourced from `reports/supplier_risk/`) to
   resolve.
3. Table view > `dim_date` > **Mark as Date Table** (Date Column =
   `full_date`) — required for the `DATEADD`/`SAMEPERIODLASTYEAR` measures
   to work; not pre-set in the TMDL because its exact serialized form
   couldn't be verified without Desktop available to confirm.
4. The 5 report pages (Executive Overview, Sales & Demand, Inventory,
   Supplier & Logistics, Scenario Simulator) exist as empty, correctly
   named/ordered canvases — build each one from
   [`report_pages_spec.md`](report_pages_spec.md) (visual-by-visual, ~5-10
   min/page). Visual JSON wasn't hand-authored for the same reason as (3):
   no Desktop available here to validate it, and broken visual JSON on
   first open would cost more time than the spec does.

Every measure lives in `_Measures` (see [`dax_measures.dax`](dax_measures.dax)
for the human-readable source; the same expressions are embedded in
`GulfMart Supply Chain.SemanticModel/definition/tables/_Measures.tmdl`)
and traces to a row in `docs/kpi_dictionary.md` — no orphan measures.
What's independently verified (in Python, against `scipy`/`src/kpi/summary.py`,
without needing Desktop) vs. best-effort (needs Desktop to confirm):

- **Verified**: every measure's underlying formula logic — including the
  two normal-distribution approximations the Scenario Simulator measures
  need (DAX has neither `NORM.S.DIST` nor `NORM.S.INV`) — via
  `tests/unit/test_dax_normal_approximations.py` and
  `tests/unit/test_dax_scenario_formulas.py`, which transcribe each DAX
  formula into Python and diff it against `scipy.stats.norm` / against
  `src/scenario_model/engine.py`'s actual output.
- **Best-effort, needs Desktop to confirm**: the TMDL/PBIR project files
  parse and open without errors, and the M queries against Postgres
  resolve correctly on your machine.
