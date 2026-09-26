# Power BI

`GulfMart Supply Chain.pbip` — a Power BI Project (TMDL semantic model +
PBIR report), not a `.pbix` (the `.pbix` a user saves from opening this is
gitignored — see `.gitignore` — same convention as everywhere else in this
repo: the reproducible source is committed, the compiled binary isn't).

Opening the project gives the full report: 14 CSV-sourced tables, 44
measures, the 3 What-If parameters, `dim_date` already marked as the date
table, and all 5 pages with their visuals built.

## Setup

1. `python powerbi/export_csv_extracts.py` — requires the Postgres
   container running (`docker compose up -d postgres`). Exports via
   `docker exec ... psql`, not a network connection to whatever host port
   is mapped — on the dev machine this was built on, a native Windows
   `postgres.exe` service was *also* listening on port 5432, silently
   intercepting connections meant for the container. Going through the
   container directly sidesteps that regardless of what's bound to the
   host port. Re-run it (after `make etl`, or whenever the warehouse
   changes), then **Refresh** in Desktop.
2. Open `GulfMart Supply Chain.pbip` in Power BI Desktop (2024+, TMDL/PBIP
   project support is GA).
3. If this checkout isn't at `E:\Delliotte\Supply-Chain-Intelligence-Risk-Analytics-Platform\`:
   **Transform Data > Manage Parameters**, set `RepoRoot` to this
   checkout's path (with a trailing `\`). It feeds every table's CSV path.
4. **Home > Refresh** to load every table from the CSVs.

Sanity check: on **Scenario Simulator**, set all 3 sliders to 0 — every
Scenario card must equal its Baseline counterpart (the calibration
property verified in `tests/unit/test_dax_scenario_formulas.py`).

## Report pages

[`build_report_visuals.py`](build_report_visuals.py) generates every
page's visuals from [`report_pages_spec.md`](report_pages_spec.md), in the
same `visual.json` format Desktop saves. Re-running it **replaces** all
visuals on all 5 pages, so run it with Desktop closed, and only when you
want the spec layout back (manual edits made in Desktop are lost).

## Lessons from opening this in Desktop

The project was first written without Desktop available, then debugged
against a real install. These are the rules that came out of it, all
load-bearing:

- **CSV extracts (`powerbi/data/*.csv`), not a live Postgres connection.**
  The `PostgreSQL.Database(...)` connector was dropped during the
  "composite model cannot be used with entity based query sources"
  debugging; CSVs also make the project open without a database.
- **A measures-only table needs a partition.** `_Measures` without one was
  the actual cause of that "composite model" error (and of "Sequence
  contains no elements"); it now has an empty `#table` partition plus a
  hidden `Column1`.
- **No standalone `//` comment lines in TMDL**; inside a DAX expression
  they're fine.
- **Property lines must stay at property indentation.** A `lineageTag:`
  indented one level deeper than the `measure` properties becomes part of
  the DAX expression and breaks the measure (and everything referencing
  it).
- **1:1 relationships need `crossFilteringBehavior: bothDirections`**, and
  ambiguous filter paths must be made inactive (see `relationships.tmdl`).
- **The report needs its base theme file** under
  `StaticResources/SharedResources/BaseThemes/`; without it Desktop fails
  with "Cannot read properties of undefined (reading 'visualContainers')"
  and shows a blank canvas.
- **What-If parameter columns are named after their table**
  (`'Demand Change Parameter'[Demand Change Parameter]`), which is what
  the `... Change % Value` measures reference.

## Measures

Every measure lives in `_Measures` (see [`dax_measures.dax`](dax_measures.dax)
for the human-readable source; the same expressions are embedded in
`GulfMart Supply Chain.SemanticModel/definition/tables/_Measures.tmdl`,
which also carries each measure's display format) and traces to a row in
`docs/kpi_dictionary.md` — no orphan measures.

The two normal-distribution approximations the Scenario Simulator
measures need (DAX has neither `NORM.S.DIST` nor `NORM.S.INV`) are
verified against `scipy.stats.norm` and against
`src/scenario_model/engine.py`'s actual output in
`tests/unit/test_dax_normal_approximations.py` and
`tests/unit/test_dax_scenario_formulas.py`.
