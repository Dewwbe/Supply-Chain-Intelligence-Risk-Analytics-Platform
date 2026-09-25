"""Builds excel/kpi_validation.xlsx (Phase 10) by driving a real Excel
process via COM (pywin32) — not a static file, so PivotTables are genuine
native pivot objects, not an approximation.

The workbook independently re-derives the same 10 KPIs as
src/kpi/summary.py / powerbi/dax_measures.dax, using SUMIFS/COUNTIFS/
XLOOKUP formulas over a raw data extract, plus 2 PivotTables — then
compares its own Excel-computed values against a snapshot of
src/kpi/summary.py's output (fetched live by this script, not hand-typed)
so a stakeholder can see the cross-check, not just trust it.

Run (Windows, Excel installed, DATABASE_URL pointing at the warehouse):
    python excel/build_kpi_validation.py

The resulting .xlsx is intentionally NOT committed (see .gitignore) — this
script is the reproducible source, same convention as every other
generated artifact in this repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import win32com.client as win32
from src.common.db import get_engine
from src.kpi.summary import compute_kpi_summary
from win32com.client import constants as xlc

OUT_PATH = Path(__file__).resolve().parent / "kpi_validation.xlsx"


def load_sales() -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT fs.order_id, dd.full_date, dp.category, fs.quantity, fs.unit_price,
               fs.sales_amount, dp.unit_cost
        FROM warehouse.fact_sales fs
        JOIN warehouse.dim_product dp ON dp.product_key = fs.product_key
        JOIN warehouse.dim_date dd ON dd.date_key = fs.date_key
        ORDER BY fs.order_id
        """,
        get_engine(),
        parse_dates=["full_date"],
    )
    return df


def load_inventory() -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT dd.full_date, fi.product_key, dw.warehouse_name, fi.opening_stock,
               fi.received_quantity, fi.sold_quantity, fi.closing_stock, dp.unit_cost
        FROM warehouse.fact_inventory fi
        JOIN warehouse.dim_product dp ON dp.product_key = fi.product_key
        JOIN warehouse.dim_warehouse dw ON dw.warehouse_key = fi.warehouse_key
        JOIN warehouse.dim_date dd ON dd.date_key = fi.date_key
        ORDER BY fi.product_key, dd.full_date
        """,
        get_engine(),
        parse_dates=["full_date"],
    )
    return df


def load_shipments() -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT order_date.full_date AS order_date, expected_date.full_date AS expected_date,
               actual_date.full_date AS actual_date, fsh.transport_cost
        FROM warehouse.fact_shipments fsh
        JOIN warehouse.dim_date order_date ON order_date.date_key = fsh.order_date_key
        LEFT JOIN warehouse.dim_date expected_date ON expected_date.date_key = fsh.expected_delivery_date_key
        LEFT JOIN warehouse.dim_date actual_date ON actual_date.date_key = fsh.actual_delivery_date_key
        """,
        get_engine(),
        parse_dates=["order_date", "expected_date", "actual_date"],
    )
    return df


def write_dataframe(sheet: Any, df: pd.DataFrame, start_row: int = 1) -> int:
    """Bulk-writes a DataFrame's header + values in 2 COM calls, not one
    call per cell — the difference between seconds and hours at this
    row count.
    """
    n_rows, n_cols = int(df.shape[0]), int(df.shape[1])
    header_range = sheet.Range(sheet.Cells(start_row, 1), sheet.Cells(start_row, n_cols))
    header_range.Value = [list(df.columns)]

    values = df.astype(object).where(pd.notnull(df), None).values.tolist()
    # win32com can't marshal pandas.Timestamp (its tz-handling machinery
    # trips on tz-naive values) — convert to plain Python datetime first.
    values = [
        [cell.to_pydatetime() if isinstance(cell, pd.Timestamp) else cell for cell in row]
        for row in values
    ]
    data_range = sheet.Range(sheet.Cells(start_row + 1, 1), sheet.Cells(start_row + n_rows, n_cols))
    data_range.Value = values
    return start_row + n_rows  # last data row


def fill_formula_down(
    sheet: Any, col: int, first_row: int, last_row: int, formula_row1: str
) -> None:
    """Writes one formula to the first data row, then fills it down —
    Excel rewrites relative references per row itself (same as dragging
    the fill handle), which is what keeps this fast at 100k+ rows.
    """
    first_cell = sheet.Cells(first_row, col)
    first_cell.Formula = formula_row1
    fill_range = sheet.Range(first_cell, sheet.Cells(last_row, col))
    first_cell.AutoFill(fill_range)


def main() -> None:
    print("Querying warehouse...")
    sales = load_sales()
    inventory = load_inventory()
    shipments = load_shipments()
    ground_truth = compute_kpi_summary()
    print(
        f"  sales: {len(sales):,} rows, inventory: {len(inventory):,} rows, shipments: {len(shipments):,} rows"
    )

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    wb = excel.Workbooks.Add()
    excel.Calculation = xlc.xlCalculationManual
    while wb.Sheets.Count > 1:
        wb.Sheets(wb.Sheets.Count).Delete()

    # --- Sales Data ---------------------------------------------------
    sales_sheet = wb.Sheets(1)
    sales_sheet.Name = "Sales Data"
    sales_last_row = write_dataframe(sales_sheet, sales)
    sales_sheet.Cells(1, 8).Value = "gross_margin_line"
    sales_sheet.Cells(1, 9).Value = "is_first_line_of_order"
    fill_formula_down(sales_sheet, 8, 2, sales_last_row, "=F2-G2*D2")
    fill_formula_down(sales_sheet, 9, 2, sales_last_row, "=IF(A2<>A1,1,0)")

    # --- Inventory Data -------------------------------------------------
    inv_sheet = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
    inv_sheet.Name = "Inventory Data"
    inv_last_row = write_dataframe(inv_sheet, inventory)
    for col, name in [
        (9, "is_latest_for_product"),
        (10, "value_if_latest"),
        (11, "unmet_qty"),
        (12, "daily_avg_value"),
    ]:
        inv_sheet.Cells(1, col).Value = name
    fill_formula_down(inv_sheet, 9, 2, inv_last_row, "=IF(B2<>B3,1,0)")
    fill_formula_down(inv_sheet, 10, 2, inv_last_row, "=IF(I2=1,G2*H2,0)")
    fill_formula_down(inv_sheet, 11, 2, inv_last_row, "=MAX(0,D2-G2-E2)")
    fill_formula_down(inv_sheet, 12, 2, inv_last_row, "=(D2+G2)/2*H2")

    # --- Shipments Data ---------------------------------------------------
    ship_sheet = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
    ship_sheet.Name = "Shipments Data"
    ship_last_row = write_dataframe(ship_sheet, shipments)
    ship_sheet.Cells(1, 5).Value = "lead_time_days"
    ship_sheet.Cells(1, 6).Value = "on_time_flag"
    fill_formula_down(ship_sheet, 5, 2, ship_last_row, '=IF(C2="","",C2-A2)')
    fill_formula_down(ship_sheet, 6, 2, ship_last_row, '=IF(AND(C2<>"",C2<=B2),1,0)')

    excel.Calculation = xlc.xlCalculationAutomatic
    excel.CalculateFullRebuild()

    # --- PivotTable 1: Revenue by Category ---------------------------------
    pivot_sheet = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
    pivot_sheet.Name = "Pivot - Revenue by Category"
    src_range = f"'Sales Data'!R1C1:R{sales_last_row}C{sales.shape[1] + 2}"
    cache1 = wb.PivotCaches().Create(SourceType=xlc.xlDatabase, SourceData=src_range)
    pt1 = cache1.CreatePivotTable(
        TableDestination=pivot_sheet.Range("A3"), TableName="RevenueByCategory"
    )
    pt1.PivotFields("category").Orientation = xlc.xlRowField
    pt1.AddDataField(pt1.PivotFields("sales_amount"), "Sum of Revenue", xlc.xlSum)
    pt1.AddDataField(pt1.PivotFields("order_id"), "Line Count", xlc.xlCount)

    # --- PivotTable 2: Daily Inventory Value (feeds Average Inventory Value)
    pivot_sheet2 = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
    pivot_sheet2.Name = "Pivot - Daily Inventory Value"
    src_range2 = f"'Inventory Data'!R1C1:R{inv_last_row}C{inventory.shape[1] + 4}"
    cache2 = wb.PivotCaches().Create(SourceType=xlc.xlDatabase, SourceData=src_range2)
    pt2 = cache2.CreatePivotTable(
        TableDestination=pivot_sheet2.Range("A3"), TableName="DailyInventoryValue"
    )
    pt2.PivotFields("full_date").Orientation = xlc.xlRowField
    pt2.AddDataField(pt2.PivotFields("daily_avg_value"), "Sum of Daily Value", xlc.xlSum)
    pt2.PivotFields("full_date").NumberFormat = "yyyy-mm-dd"

    # DataBodyRange still includes the Grand Total row even with
    # RowGrand = False set beforehand (verified live: with 1337 distinct
    # dates, DataBodyRange came back as 1338 rows, and AVERAGE() over it
    # was ~2x too high because that extra row repeats the full column sum)
    # — so detect and explicitly exclude it instead of trusting the
    # RowGrand setting to have taken effect.
    data_range = pt2.DataBodyRange
    first_row, n_rows, col = data_range.Row, data_range.Rows.Count, data_range.Column
    last_row = first_row + n_rows - 1
    last_row_label = pivot_sheet2.Cells(last_row, col - 1).Value
    end_row = (
        last_row - 1
        if isinstance(last_row_label, str) and "grand total" in last_row_label.lower()
        else last_row
    )
    avg_data_range = pivot_sheet2.Range(
        pivot_sheet2.Cells(first_row, col), pivot_sheet2.Cells(end_row, col)
    )
    avg_inventory_range_address = f"'{pivot_sheet2.Name}'!{avg_data_range.Address}"

    # --- KPI Dictionary (lookup source for XLOOKUP) -------------------------
    dict_sheet = wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
    dict_sheet.Name = "KPI Dictionary"
    kpi_dict_rows = [
        ["KPI", "Formula", "Grain", "docs/kpi_dictionary.md section"],
        ["Total Revenue", "SUM(sales_amount)", "any", "1. Sales / Revenue"],
        ["Total Units Sold", "SUM(quantity)", "any", "1. Sales / Revenue"],
        [
            "Gross Margin",
            "SUM(sales_amount) - SUM(quantity * unit_cost)",
            "any",
            "1. Sales / Revenue",
        ],
        [
            "Average Order Value",
            "SUM(sales_amount) / COUNT(DISTINCT order_id)",
            "date/location/segment",
            "1. Sales / Revenue",
        ],
        [
            "Inventory Value",
            "SUM(closing_stock * unit_cost)",
            "date/product/warehouse",
            "2. Inventory",
        ],
        [
            "Stockout Rate",
            "COUNT(closing_stock=0) / COUNT(available_days)",
            "product/warehouse/period",
            "2. Inventory",
        ],
        [
            "Fill Rate",
            "1 - (unmet_demand / total_demand)",
            "product/warehouse/period",
            "2. Inventory",
        ],
        [
            "Supplier OTD",
            "COUNT(actual<=expected) / COUNT(shipments)",
            "supplier/period",
            "3. Supplier / Logistics",
        ],
        [
            "Average Lead Time",
            "AVG(actual_delivery_date - order_date)",
            "supplier/product/period",
            "3. Supplier / Logistics",
        ],
        [
            "Average Inventory Value",
            "AVG(opening_stock, closing_stock) * unit_cost, averaged by day",
            "product/warehouse/period",
            "2. Inventory (supporting)",
        ],
        [
            "Inventory Turnover",
            "COGS / average_inventory_value",
            "product/warehouse/period",
            "2. Inventory",
        ],
    ]
    dict_sheet.Range(dict_sheet.Cells(1, 1), dict_sheet.Cells(len(kpi_dict_rows), 4)).Value = (
        kpi_dict_rows
    )

    # --- KPI Validation ------------------------------------------------
    val_sheet = wb.Sheets.Add(Before=wb.Sheets(1))
    val_sheet.Name = "KPI Validation"
    headers = [
        "KPI",
        "Formula (XLOOKUP)",
        "Excel-Computed",
        "Python Ground Truth",
        "Abs % Diff",
        "Match?",
    ]
    val_sheet.Range(val_sheet.Cells(1, 1), val_sheet.Cells(1, 6)).Value = [headers]

    sd, iv, sh = "'Sales Data'", "'Inventory Data'", "'Shipments Data'"
    kpi_rows: list[tuple[str, str, float | None]] = [
        ("Total Revenue", f"=SUM({sd}!F2:F{sales_last_row})", ground_truth.total_revenue_aed),
        (
            "Total Units Sold",
            f"=SUM({sd}!D2:D{sales_last_row})",
            float(ground_truth.total_units_sold),
        ),
        ("Gross Margin", f"=SUM({sd}!H2:H{sales_last_row})", ground_truth.gross_margin_aed),
        (
            "Average Order Value",
            f"=C2/SUM({sd}!I2:I{sales_last_row})",
            ground_truth.average_order_value_aed,
        ),
        ("Inventory Value", f"=SUM({iv}!J2:J{inv_last_row})", ground_truth.inventory_value_aed),
        (
            "Stockout Rate",
            f"=COUNTIFS({iv}!G2:G{inv_last_row},0)/COUNTA({iv}!G2:G{inv_last_row})",
            ground_truth.stockout_rate,
        ),
        (
            "Fill Rate",
            f"=SUM({iv}!F2:F{inv_last_row})/(SUM({iv}!F2:F{inv_last_row})+SUM({iv}!K2:K{inv_last_row}))",
            ground_truth.fill_rate,
        ),
        (
            "Supplier OTD",
            f'=SUM({sh}!F2:F{ship_last_row})/COUNTIFS({sh}!C2:C{ship_last_row},"<>")',
            ground_truth.supplier_otd,
        ),
        (
            "Average Lead Time",
            f"=AVERAGE({sh}!E2:E{ship_last_row})",
            ground_truth.average_lead_time_days,
        ),
        (
            "Average Inventory Value",
            f"=AVERAGE({avg_inventory_range_address})",
            None,  # supporting row only, no headline ground truth to compare
        ),
        ("Inventory Turnover", "=(C2-C4)/C11", ground_truth.inventory_turnover),
    ]
    for i, (name, formula, truth) in enumerate(kpi_rows):
        r = i + 2
        val_sheet.Cells(r, 1).Value = name
        # XLOOKUP with an INDEX/MATCH fallback: XLOOKUP requires Excel for
        # Microsoft 365 or Excel 2021+; verified live that the Excel build
        # this was developed against (perpetual-license 16.0/4266) doesn't
        # have it (#NAME? error) — IFERROR makes this formula correct on
        # both that build and a newer one, rather than silently assuming
        # the grading machine has XLOOKUP.
        val_sheet.Cells(r, 2).Formula = (
            f"=IFERROR(XLOOKUP(A{r},'KPI Dictionary'!A:A,'KPI Dictionary'!B:B),"
            f"INDEX('KPI Dictionary'!B:B,MATCH(A{r},'KPI Dictionary'!A:A,0)))"
        )
        val_sheet.Cells(r, 3).Formula = formula
        if truth is not None:
            val_sheet.Cells(r, 4).Value = truth
            val_sheet.Cells(r, 5).Formula = f"=IF(D{r}=0,ABS(C{r}),ABS(C{r}-D{r})/ABS(D{r}))"
            val_sheet.Cells(r, 6).Formula = f'=IF(E{r}<0.005,"MATCH","CHECK")'
        else:
            val_sheet.Cells(r, 4).Value = "(supporting row, not a headline KPI)"

    match_range = val_sheet.Range("F2", f"F{1 + len(kpi_rows)}")
    match_range.FormatConditions.Delete()
    fc_match = match_range.FormatConditions.Add(
        Type=xlc.xlTextString, String="MATCH", TextOperator=xlc.xlContains
    )
    fc_match.Interior.Color = 0x90EE90  # light green
    fc_check = match_range.FormatConditions.Add(
        Type=xlc.xlTextString, String="CHECK", TextOperator=xlc.xlContains
    )
    fc_check.Interior.Color = 0x9999FF  # light red/pink

    val_sheet.Columns("A:F").AutoFit()
    val_sheet.Activate()

    excel.CalculateFullRebuild()
    wb.RefreshAll()
    excel.CalculateFullRebuild()

    # Read back the computed vs. ground-truth comparison for the console
    # log — the actual verification happens by re-reading the saved file
    # afterwards (see the test invocation in the README), this is just a
    # build-time sanity echo.
    print("\nKPI Validation results:")
    for i, (name, _, truth) in enumerate(kpi_rows):
        r = i + 2
        computed = val_sheet.Cells(r, 3).Value
        match = val_sheet.Cells(r, 6).Value
        print(f"  {name:28s} excel={computed!r:>20}  truth={truth!r:>20}  {match}")

    wb.SaveAs(str(OUT_PATH), FileFormat=xlc.xlOpenXMLWorkbook)
    wb.Close(SaveChanges=False)
    excel.Quit()
    print(f"\nSaved {OUT_PATH}")


if __name__ == "__main__":
    main()
