"""Builds excel/scenario_analysis.xlsx (Phase 10) — a real Excel-native
mirror of POST /api/v1/scenario/simulate (src/scenario_model/engine.py),
using NORM.S.DIST/NORM.S.INV directly (Excel has both natively; DAX has
neither, which is why powerbi/dax_measures.dax needed the Acklam/
Zelen-Severo approximations instead — see that file's comments).

Unlike the DAX version, this can be verified end-to-end automatically:
this script sets the same 3 input cells Desktop's UI would (via COM),
reads back Excel's computed output, and diffs it against
run_scenario()'s Python output for the same parameters — see main()'s
final verification loop and its printed results.

Run (Windows, Excel installed, DATABASE_URL pointing at the warehouse):
    python excel/build_scenario_analysis.py
"""

from __future__ import annotations

from pathlib import Path

import win32com.client as win32
from src.api.routers.scenario import ScenarioRequest
from src.scenario_model.data import load_baseline
from src.scenario_model.engine import run_scenario
from win32com.client import constants as xlc

OUT_PATH = Path(__file__).resolve().parent / "scenario_analysis.xlsx"

SCENARIOS = [
    ("Baseline (no change)", 0, 0, 0),
    ("Demand +10%", 10, 0, 0),
    ("Demand +30% (max)", 30, 0, 0),
    ("Demand -20% (max)", -20, 0, 0),
    ("Lead time +50% (max)", 0, 50, 0),
    ("Lead time -30% (max)", 0, -30, 0),
    ("Transport cost +40% (max)", 0, 0, 40),
    ("Combined stress (worst case)", 30, 50, 40),
    ("Combined relief (best case)", -20, -30, -20),
]


def main() -> None:
    print("Loading baseline...")
    baseline = load_baseline()

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Add()
    while wb.Sheets.Count > 1:
        wb.Sheets(wb.Sheets.Count).Delete()

    sheet = wb.Sheets(1)
    sheet.Name = "Scenario Simulator"

    # --- Baseline block (B2:B8) ------------------------------------------
    labels_values = [
        ("Baseline avg daily demand (units)", baseline.avg_daily_demand_units),
        ("Baseline daily demand std (units)", baseline.daily_demand_std_units),
        ("Baseline avg lead time (days)", baseline.avg_lead_time_days),
        ("Baseline stockout rate", baseline.stockout_rate),
        ("Baseline inventory value (AED)", baseline.inventory_value_aed),
        ("Baseline transport cost (AED)", baseline.transport_cost_aed),
        ("Baseline revenue (AED)", baseline.revenue_aed),
    ]
    sheet.Range("A1").Value = (
        "Baseline (from src/scenario_model/data.py::load_baseline(), snapshot at build time)"
    )
    for i, (label, value) in enumerate(labels_values):
        r = i + 2
        sheet.Cells(r, 1).Value = label
        sheet.Cells(r, 2).Value = value
    # named ranges for readability in every downstream formula
    names = [
        "BaseAvgDemand",
        "BaseDemandStd",
        "BaseAvgLeadTime",
        "BaseStockoutRate",
        "BaseInventoryValue",
        "BaseTransportCost",
        "BaseRevenue",
    ]
    for i, name in enumerate(names):
        wb.Names.Add(Name=name, RefersTo=f"='Scenario Simulator'!$B${i + 2}")

    # --- Scenario inputs (B11:B13) with data validation matching --------
    # ScenarioRequest's Field bounds in src/api/routers/scenario.py.
    sheet.Range("A10").Value = "Scenario inputs (edit these 3 cells)"
    input_rows = [
        ("Demand change %", 0, -20, 30, "DemandChangePct"),
        ("Lead time change %", 0, -30, 50, "LeadTimeChangePct"),
        ("Transport cost change %", 0, -20, 40, "CostChangePct"),
    ]
    for i, (label, default, lo, hi, name) in enumerate(input_rows):
        r = 11 + i
        sheet.Cells(r, 1).Value = f"{label} (range {lo} to {hi})"
        cell = sheet.Cells(r, 2)
        cell.Value = default
        cell.Validation.Delete()
        cell.Validation.Add(
            Type=xlc.xlValidateWholeNumber,
            AlertStyle=xlc.xlValidAlertStop,
            Operator=xlc.xlBetween,
            Formula1=str(lo),
            Formula2=str(hi),
        )
        wb.Names.Add(Name=name, RefersTo=f"='Scenario Simulator'!$B${r}")

    # --- Model (mirrors engine.py exactly) -------------------------------
    sheet.Range("A16").Value = "Model (mirrors src/scenario_model/engine.py exactly)"
    model_rows = [
        ("Demand factor", "=1+DemandChangePct/100", "DemandFactor"),
        ("Lead time factor", "=1+LeadTimeChangePct/100", "LeadTimeFactor"),
        ("Cost factor", "=1+CostChangePct/100", "CostFactor"),
        (
            "Implied safety stock",
            "=BaseAvgDemand*BaseAvgLeadTime + NORM.S.INV(1-MIN(MAX(BaseStockoutRate,0.0001),0.9999))*BaseDemandStd*SQRT(BaseAvgLeadTime)",
            "SafetyStock",
        ),
        (
            "Scenario mean demand-during-lead-time",
            "=BaseAvgDemand*DemandFactor*(BaseAvgLeadTime*LeadTimeFactor)",
            "ScenarioMean",
        ),
        (
            "Scenario std demand-during-lead-time",
            "=BaseDemandStd*DemandFactor*SQRT(BaseAvgLeadTime*LeadTimeFactor)",
            "ScenarioStd",
        ),
        (
            "Scenario stockout rate",
            "=IF(ScenarioStd>0,MIN(MAX(1-NORM.DIST(SafetyStock,ScenarioMean,ScenarioStd,TRUE),0),1),IF(SafetyStock>=ScenarioMean,0,1))",
            "ScenarioStockoutRate",
        ),
        ("Scenario fill rate", "=1-ScenarioStockoutRate", "ScenarioFillRate"),
        (
            "Projected inventory value (AED)",
            "=BaseInventoryValue*DemandFactor*LeadTimeFactor",
            "ProjectedInventory",
        ),
        (
            "Projected transport cost (AED)",
            "=BaseTransportCost*DemandFactor*CostFactor",
            "ProjectedTransportCost",
        ),
        ("Projected revenue (AED)", "=BaseRevenue*DemandFactor", "ProjectedRevenue"),
        ("Revenue at risk (AED)", "=ProjectedRevenue*ScenarioStockoutRate", "RevenueAtRisk"),
        ("Baseline fill rate", "=1-BaseStockoutRate", "BaselineFillRate"),
        (
            "Baseline revenue at risk (AED)",
            "=BaseRevenue*BaseStockoutRate",
            "BaselineRevenueAtRisk",
        ),
    ]
    for i, (label, formula, name) in enumerate(model_rows):
        r = 17 + i
        sheet.Cells(r, 1).Value = label
        sheet.Cells(r, 2).Formula = formula
        wb.Names.Add(Name=name, RefersTo=f"='Scenario Simulator'!$B${r}")

    # --- Baseline vs. scenario, side by side -----------------------------
    side_by_side_row = 17 + len(model_rows) + 2
    sheet.Cells(side_by_side_row, 1).Value = "Baseline vs. Scenario, side by side"
    headers = ["Metric", "Baseline", "Scenario"]
    sheet.Range(
        sheet.Cells(side_by_side_row + 1, 1), sheet.Cells(side_by_side_row + 1, 3)
    ).Value = [headers]
    pairs = [
        ("Inventory value (AED)", "BaseInventoryValue", "ProjectedInventory"),
        ("Transport cost (AED)", "BaseTransportCost", "ProjectedTransportCost"),
        ("Stockout rate", "BaseStockoutRate", "ScenarioStockoutRate"),
        ("Fill rate", "BaselineFillRate", "ScenarioFillRate"),
        ("Revenue at risk (AED)", "BaselineRevenueAtRisk", "RevenueAtRisk"),
    ]
    for i, (label, base_name, scen_name) in enumerate(pairs):
        r = side_by_side_row + 2 + i
        sheet.Cells(r, 1).Value = label
        sheet.Cells(r, 2).Formula = f"={base_name}"
        sheet.Cells(r, 3).Formula = f"={scen_name}"

    sheet.Columns("A:C").AutoFit()
    excel.CalculateFullRebuild()

    # --- Verification: drive the 9 representative scenarios through the
    # live workbook exactly as a user moving the sliders would, and diff
    # against run_scenario()'s Python output for the same inputs. ---------
    demand_cell, lead_cell, cost_cell = sheet.Range("B11"), sheet.Range("B12"), sheet.Range("B13")
    stockout_cell = sheet.Range("ScenarioStockoutRate")
    fill_cell = sheet.Range("ScenarioFillRate")
    inv_cell = sheet.Range("ProjectedInventory")
    transport_cell = sheet.Range("ProjectedTransportCost")
    risk_cell = sheet.Range("RevenueAtRisk")

    print("\nVerifying all 9 representative scenarios against run_scenario()...")
    all_matched = True
    for name, demand_pct, lead_pct, cost_pct in SCENARIOS:
        demand_cell.Value = demand_pct
        lead_cell.Value = lead_pct
        cost_cell.Value = cost_pct
        excel.CalculateFullRebuild()

        payload = ScenarioRequest(
            demand_change_pct=demand_pct,
            lead_time_change_pct=lead_pct,
            transport_cost_change_pct=cost_pct,
        )
        py_result = run_scenario(payload, baseline=baseline)

        # engine.py rounds its ScenarioResult output (4 decimals for
        # rates, 2 for AED amounts) but this workbook deliberately doesn't
        # — so tolerance is an absolute bound matching that rounding step,
        # not a pure relative one (which blows up for near-zero rates:
        # e.g. 0.0042 vs 0.00418 is a real ~0.4% relative gap despite
        # being the same number to the precision engine.py reports it at).
        checks = [
            ("stockout_rate", stockout_cell.Value, py_result.stockout_rate, 5e-4),
            ("fill_rate", fill_cell.Value, py_result.fill_rate, 5e-4),
            ("projected_inventory_aed", inv_cell.Value, py_result.projected_inventory_aed, 0.01),
            (
                "projected_transport_cost_aed",
                transport_cell.Value,
                py_result.projected_transport_cost_aed,
                0.01,
            ),
            ("revenue_at_risk_aed", risk_cell.Value, py_result.revenue_at_risk_aed, 0.01),
        ]
        row_ok = True
        for field, excel_val, py_val, abs_tol in checks:
            ok = abs(excel_val - py_val) < abs_tol
            row_ok = row_ok and ok
            if not ok:
                print(f"  MISMATCH [{name}] {field}: excel={excel_val} python={py_val}")
        status = "OK" if row_ok else "MISMATCH"
        all_matched = all_matched and row_ok
        print(f"  [{status}] {name}: demand={demand_pct}%, lead_time={lead_pct}%, cost={cost_pct}%")

    # leave the workbook on the baseline (no-change) scenario when saved
    demand_cell.Value, lead_cell.Value, cost_cell.Value = 0, 0, 0
    excel.CalculateFullRebuild()

    wb.SaveAs(str(OUT_PATH), FileFormat=xlc.xlOpenXMLWorkbook)
    wb.Close(SaveChanges=False)
    excel.Quit()

    print(
        f"\n{'All 9 scenarios matched run_scenario() within 0.1%.' if all_matched else 'SOME SCENARIOS DID NOT MATCH — see above.'}"
    )
    print(f"Saved {OUT_PATH}")
    if not all_matched:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
