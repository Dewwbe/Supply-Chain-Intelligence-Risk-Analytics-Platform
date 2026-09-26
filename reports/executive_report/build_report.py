"""Builds the Phase 11 executive report: evidence tables, figures, Markdown and PDF.

Every number the report cites is computed here, from the warehouse extract
(`powerbi/data/*.csv`, regenerate with `python powerbi/export_csv_extracts.py`)
and the committed outputs of earlier phases (`reports/*`, `notebooks/06`), then
substituted into `executive_report.template.md` as `{{name}}` placeholders. A
placeholder with no computed value fails the build instead of rendering blank.

Outputs (all in this folder):
  evidence/*.csv          tables the recommendations cite
  figures/*.png           charts embedded in the report
  executive_report.md     the rendered report (readable on GitHub)
  executive_report.pdf    the deliverable, printed by headless Microsoft Edge

Run: python reports/executive_report/build_report.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import markdown
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "powerbi" / "data"
FIGURES = HERE / "figures"
EVIDENCE = HERE / "evidence"
EDGE_PATHS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

sys.path.insert(0, str(REPO))
from etl.synthesize import inventory as inventory_sim  # noqa: E402
from etl.synthesize.rng import hash_to_range  # noqa: E402

BLUE, ORANGE, GREY, RED, GREEN = "#1f5f8b", "#d9713c", "#8a8f98", "#c0392b", "#4c9a5b"


def aed(value: float) -> str:
    """AED amount in millions (>= 1M) or thousands, for prose."""
    if abs(value) >= 1e6:
        return f"AED {value / 1e6:,.2f}M"
    return f"AED {value / 1e3:,.0f}k"


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


# --- data ------------------------------------------------------------------


def load_extract() -> dict[str, pd.DataFrame]:
    missing = [t for t in ("fact_sales", "fact_inventory") if not (DATA / f"{t}.csv").exists()]
    if missing:
        sys.exit(f"Missing {missing} in {DATA} - run python powerbi/export_csv_extracts.py first.")
    dates = pd.read_csv(DATA / "dim_date.csv", usecols=["date_key", "full_date"])
    dates["full_date"] = pd.to_datetime(dates["full_date"])
    products = pd.read_csv(
        DATA / "dim_product.csv",
        usecols=["product_key", "product_source_id", "category", "unit_cost", "unit_price"],
        dtype={"product_source_id": str},
    )
    sales = pd.read_csv(
        DATA / "fact_sales.csv",
        usecols=[
            "sales_key",
            "source_system",
            "order_id",
            "date_key",
            "product_key",
            "quantity",
            "sales_amount",
        ],
        dtype={"order_id": str},
    )
    sales = sales.merge(dates, on="date_key").merge(products, on="product_key")
    inventory = pd.read_csv(DATA / "fact_inventory.csv").merge(dates, on="date_key")
    inventory = inventory.merge(products, on="product_key")
    shipments = pd.read_csv(
        DATA / "fact_shipments.csv",
        usecols=["order_date_key", "expected_delivery_date_key", "actual_delivery_date_key"],
    )
    return {"sales": sales, "inventory": inventory, "shipments": shipments, "dates": dates}


# --- evidence ----------------------------------------------------------------


def headline_kpis(d: dict[str, pd.DataFrame]) -> dict[str, float]:
    """The 10 headline KPIs, same definitions as src/kpi/summary.py."""
    sales, inv, ship, dates = d["sales"], d["inventory"], d["shipments"], d["dates"]
    revenue = sales["sales_amount"].sum()
    cogs = (sales["quantity"] * sales["unit_cost"]).sum()

    latest = inv.sort_values("full_date").groupby("product_key").tail(1)
    inventory_value = (latest["closing_stock"] * latest["unit_cost"]).sum()
    daily_value = (
        ((inv["opening_stock"] + inv["closing_stock"]) / 2 * inv["unit_cost"])
        .groupby(inv["full_date"])
        .sum()
    )

    demand = sales.groupby(["product_key", "date_key"])["quantity"].sum().rename("demand")
    inv_demand = inv.join(demand, on=["product_key", "date_key"])["demand"].fillna(0)

    date_of = dates.set_index("date_key")["full_date"]
    delivered = ship["actual_delivery_date_key"].notna()
    lead_days = (
        ship.loc[delivered, "actual_delivery_date_key"].map(date_of)
        - ship.loc[delivered, "order_date_key"].map(date_of)
    ).dt.days
    on_time = ship["actual_delivery_date_key"] <= ship["expected_delivery_date_key"]

    return {
        "total_revenue": revenue,
        "gross_margin": revenue - cogs,
        "gross_margin_pct": (revenue - cogs) / revenue,
        "total_units": sales["quantity"].sum(),
        "aov": revenue / sales["order_id"].nunique(),
        "inventory_value": inventory_value,
        "stockout_rate": (inv["closing_stock"] == 0).mean(),
        "fill_rate": inv["sold_quantity"].sum() / inv_demand.sum(),
        "units_demanded": inv_demand.sum(),
        "units_fulfilled": inv["sold_quantity"].sum(),
        "supplier_otd": (on_time & delivered).sum() / delivered.sum(),
        "avg_lead_time": lead_days.mean(),
        "inventory_turnover": cogs / daily_value.mean(),
    }


def product_lead_time(product_source_id: str) -> int:
    """The replenishment lead time etl/synthesize/inventory.py assigned this product."""
    return round(
        hash_to_range(
            f"inv_lead_time:{product_source_id}",
            inventory_sim.MIN_LEAD_DAYS,
            inventory_sim.MAX_LEAD_DAYS,
        )
    )


def lead_time_vs_stockout(inv: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    per_product = (
        inv.groupby("product_source_id")["closing_stock"]
        .apply(lambda s: (s == 0).mean())
        .rename("stockout_rate")
        .reset_index()
    )
    per_product["lead_time_days"] = per_product["product_source_id"].map(product_lead_time)
    rho = per_product[["lead_time_days", "stockout_rate"]].corr(method="spearman").iloc[0, 1]
    per_product["band"] = pd.cut(
        per_product["lead_time_days"],
        [2, 7, 10, 14],
        labels=["3-7 days", "8-10 days", "11-14 days"],
    )
    bands = (
        per_product.groupby("band", observed=True)
        .agg(products=("stockout_rate", "size"), stockout_rate=("stockout_rate", "mean"))
        .reset_index()
    )
    return bands, float(rho)


def simulate_policy(sales: pd.DataFrame, reorder_days, target_days) -> dict[str, float]:
    """Re-runs the Phase 3 inventory simulator with a different (s, S) policy.

    Same code, same real demand, same per-product lead times; only the
    reorder point / order-up-to level (in days of average demand) change.
    """
    original = inventory_sim._simulate_one_product

    def simulate(product_source_id: str, daily_sold: pd.Series) -> pd.DataFrame:
        lead_time = product_lead_time(product_source_id)
        inventory_sim.REORDER_POINT_DAYS = reorder_days(lead_time)
        inventory_sim.TARGET_STOCK_DAYS = target_days(lead_time)
        return original(product_source_id, daily_sold)

    inventory_sim._simulate_one_product = simulate
    try:
        result = inventory_sim.build_inventory(
            sales[["product_source_id", "full_date", "quantity"]].rename(
                columns={"full_date": "order_date"}
            )
        )
    finally:
        inventory_sim._simulate_one_product = original
        inventory_sim.REORDER_POINT_DAYS, inventory_sim.TARGET_STOCK_DAYS = 7, 30

    prices = sales.drop_duplicates("product_source_id").set_index("product_source_id")
    result["value"] = result["closing_stock"] * result["product_source_id"].map(prices["unit_cost"])
    demand = sales.groupby(["product_source_id", "full_date"])["quantity"].sum().rename("demand")
    demanded = result.join(demand, on=["product_source_id", "date"])["demand"].fillna(0)
    return {
        "stockout_rate": (result["closing_stock"] == 0).mean(),
        "fill_rate": result["sold_quantity"].sum() / demanded.sum(),
        "units_fulfilled": result["sold_quantity"].sum(),
        "revenue_fulfilled_aed": (
            result["sold_quantity"] * result["product_source_id"].map(prices["unit_price"])
        ).sum(),
        "avg_inventory_value_aed": result.groupby("date")["value"].sum().mean(),
    }


def forecast_comparison() -> pd.DataFrame:
    """The model comparison table printed by notebooks/06_demand_forecasting.ipynb §4."""
    nb = json.loads((REPO / "notebooks" / "06_demand_forecasting.ipynb").read_text("utf-8"))
    for cell in nb["cells"]:
        for output in cell.get("outputs", []):
            text = "".join(output.get("data", {}).get("text/plain", ""))
            if "avg_interval_width" in text and "product_name" not in text:
                lines = [ln for ln in text.splitlines() if ln.strip() and ln.strip() != "model"]
                header = lines[0].split()
                # "Seasonal Naive 55.20 89.76 ..." -> the last len(header) tokens
                # are the metrics, everything before them is the model name
                tokens = [ln.split() for ln in lines[1:]]
                n = len(header)
                table = pd.DataFrame(
                    [t[-n:] for t in tokens], index=[" ".join(t[:-n]) for t in tokens]
                )
                table.columns = header
                return table.astype(float)
    raise RuntimeError("Forecast comparison table not found in notebook 06 outputs.")


# --- figures -----------------------------------------------------------------


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=160)
    plt.close(fig)


def figure_monthly_revenue(sales: pd.DataFrame) -> None:
    monthly = (
        sales.groupby([sales["full_date"].dt.to_period("M"), "source_system"])["sales_amount"]
        .sum()
        .unstack(fill_value=0)
        / 1e6
    )
    fig, ax = plt.subplots(figsize=(9, 3.2))
    monthly.index = monthly.index.to_timestamp()
    ax.stackplot(
        monthly.index,
        monthly["dataco"],
        monthly["olist"],
        labels=["DataCo source", "Olist source"],
        colors=[BLUE, ORANGE],
        alpha=0.85,
    )
    ax.set_ylabel("Revenue (AED M)")
    ax.set_title("Monthly revenue by source dataset")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "fig1_monthly_revenue.png")


def figure_categories(sales: pd.DataFrame) -> pd.DataFrame:
    by_cat = sales.assign(cost=sales["quantity"] * sales["unit_cost"]).groupby("category")
    table = by_cat.agg(revenue=("sales_amount", "sum"), cost=("cost", "sum"))
    table["share"] = table["revenue"] / table["revenue"].sum()
    table["margin_pct"] = (table["revenue"] - table["cost"]) / table["revenue"]
    top = table.sort_values("revenue", ascending=False).head(10)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    bars = ax.barh(top.index[::-1], top["share"][::-1] * 100, color=BLUE)
    for bar, margin in zip(bars, top["margin_pct"][::-1], strict=True):
        ax.text(
            bar.get_width() + 0.2,
            bar.get_y() + bar.get_height() / 2,
            f"margin {margin * 100:.0f}%",
            va="center",
            fontsize=8,
            color=GREY,
        )
    ax.set_xlabel("Share of total revenue (%)")
    ax.set_title("Top 10 categories: revenue share and gross margin")
    ax.set_xlim(0, top["share"].max() * 100 * 1.35)
    save(fig, "fig2_categories.png")
    return table.sort_values("revenue", ascending=False)


def figure_lead_time(bands: pd.DataFrame, policies: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.4))
    ax1.bar(bands["band"].astype(str), bands["stockout_rate"] * 100, color=[GREEN, ORANGE, RED])
    for i, row in bands.iterrows():
        ax1.text(i, row["stockout_rate"] * 100 + 0.4, pct(row["stockout_rate"]), ha="center")
    ax1.set_ylabel("Stockout rate (% of days)")
    ax1.set_xlabel("Replenishment lead time")
    ax1.set_title("Stockouts rise with lead time")

    ax2.plot(
        policies["avg_inventory_value_aed"] / 1e6,
        policies["stockout_rate"] * 100,
        marker="o",
        color=BLUE,
    )
    for _, row in policies.iterrows():
        ax2.annotate(
            row["policy"],
            (row["avg_inventory_value_aed"] / 1e6, row["stockout_rate"] * 100),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
        )
    ax2.set_ylim(0, policies["stockout_rate"].max() * 100 * 1.2)
    ax2.set_xlabel("Average inventory value (AED M)")
    ax2.set_ylabel("Stockout rate (% of days)")
    ax2.set_title("Reorder-point policy trade-off")
    ax2.set_xlim(
        policies["avg_inventory_value_aed"].min() / 1e6 * 0.9,
        policies["avg_inventory_value_aed"].max() / 1e6 * 1.25,
    )
    save(fig, "fig3_lead_time_policy.png")


def figure_supplier_risk(risk: pd.DataFrame) -> None:
    colors = {"Low": GREEN, "Medium": "#d4a72c", "High": ORANGE, "Critical": RED}
    ordered = risk.sort_values("risk_score")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.barh(
        ordered["supplier_id"].str.replace("  ", " "),
        ordered["risk_score"],
        color=ordered["risk_level"].map(colors),
    )
    ax.set_xlabel("Risk score (0-100, relative to current supplier base)")
    ax.set_title("Supplier risk score (colour = risk level)")
    save(fig, "fig4_supplier_risk.png")


def figure_forecast(table: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.0))
    ax1.bar(table.index, table["WAPE"], color=BLUE)
    ax1.set_ylabel("WAPE (%)")
    ax1.set_title("Point accuracy (lower is better)")
    ax1.set_ylim(table["WAPE"].min() * 0.9, table["WAPE"].max() * 1.05)
    ax2.bar(table.index, table["interval_coverage"] * 100, color=ORANGE)
    ax2.axhline(80, color="black", linestyle="--", linewidth=1, label="Stated 80% interval")
    ax2.set_ylabel("Actuals inside interval (%)")
    ax2.set_title("Interval calibration (target 80%)")
    ax2.legend(frameon=False, fontsize=8, loc="lower right")
    for ax in (ax1, ax2):
        ax.tick_params(axis="x", labelsize=8)
    save(fig, "fig5_forecast.png")


def figure_scenarios(scenarios: pd.DataFrame) -> None:
    ordered = scenarios.sort_values("stockout_rate")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    colors = [GREY if "Baseline" in s else BLUE for s in ordered["scenario"]]
    ax.barh(ordered["scenario"], ordered["stockout_rate"] * 100, color=colors)
    ax.axvline(scenarios.iloc[0]["stockout_rate"] * 100, color="black", linestyle="--", lw=1)
    ax.set_xlabel("Modelled stockout probability (%)")
    ax.set_title("Scenario engine: stockout probability by scenario")
    save(fig, "fig6_scenarios.png")


# --- render ------------------------------------------------------------------

CSS = """
@page { size: A4; margin: 18mm 17mm 18mm 17mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.2pt; line-height: 1.45;
       color: #1d2530; }
h1 { font-size: 22pt; color: #1f5f8b; margin: 0 0 4pt 0; }
h2 { font-size: 14pt; color: #1f5f8b; border-bottom: 1.5px solid #1f5f8b; padding-bottom: 2pt;
     margin-top: 18pt; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt 0; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; font-size: 9pt;
        break-inside: avoid; }
th { background: #1f5f8b; color: white; text-align: left; padding: 4pt 6pt; }
td { border-bottom: 1px solid #d5dbe3; padding: 3.5pt 6pt; vertical-align: top; }
tr:nth-child(even) td { background: #f4f7fa; }
img { width: 100%; break-inside: avoid; margin: 4pt 0; }
p, li { orphans: 3; widows: 3; }
blockquote { border-left: 3px solid #d9713c; margin: 8pt 0; padding: 4pt 10pt;
             background: #fdf4ee; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #eef1f5;
       padding: 0 2pt; }
.pagebreak { break-after: page; }
.cover { height: 240mm; display: flex; flex-direction: column; justify-content: center; }
.cover .sub { font-size: 13pt; color: #555; margin-bottom: 26pt; }
.cover .meta { font-size: 10pt; color: #555; }
.caption { font-size: 8.5pt; color: #666; margin: -2pt 0 10pt 0; }
"""


def render(values: dict[str, str]) -> Path:
    template = (HERE / "executive_report.template.md").read_text(encoding="utf-8")
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", template)) - values.keys())
    if missing:
        sys.exit(f"Template placeholders with no computed value: {missing}")
    rendered = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)
    (HERE / "executive_report.md").write_text(rendered, encoding="utf-8")

    body = markdown.markdown(rendered, extensions=["tables", "md_in_html"])
    html_path = HERE / "executive_report.html"
    html_path.write_text(
        f'<!doctype html><html><head><meta charset="utf-8"><title>GulfMart Executive Report'
        f"</title><style>{CSS}</style></head><body>{body}</body></html>",
        encoding="utf-8",
    )
    edge = next((p for p in EDGE_PATHS if p.exists()), None)
    if edge is None:
        sys.exit("Microsoft Edge not found; open executive_report.html and print to PDF.")
    pdf_path = HERE / "executive_report.pdf"
    subprocess.run(
        [
            str(edge),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    html_path.unlink()
    return pdf_path


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    print("Loading warehouse extract...")
    d = load_extract()
    sales, inv = d["sales"], d["inventory"]

    kpi = headline_kpis(d)
    categories = figure_categories(sales)
    figure_monthly_revenue(sales)

    bands, rho = lead_time_vs_stockout(inv)
    bands.to_csv(EVIDENCE / "lead_time_vs_stockout.csv", index=False)

    print("Re-running the inventory simulator under 3 reorder policies...")
    policy_specs = [
        ("Current: reorder at 7d", lambda lt: 7, lambda lt: 30),
        ("Lead time + 3d", lambda lt: lt + 3, lambda lt: max(30, lt + 26)),
        ("Lead time + 7d", lambda lt: lt + 7, lambda lt: max(30, lt + 30)),
    ]
    policies = pd.DataFrame(
        [{"policy": name, **simulate_policy(sales, rp, tgt)} for name, rp, tgt in policy_specs]
    )
    policies.to_csv(EVIDENCE / "reorder_policy_simulation.csv", index=False)
    figure_lead_time(bands, policies)

    risk = pd.read_csv(REPO / "reports" / "supplier_risk" / "supplier_risk_scores.csv")
    figure_supplier_risk(risk)
    forecast = forecast_comparison()
    forecast.to_csv(EVIDENCE / "forecast_model_comparison.csv")
    figure_forecast(forecast)
    scenarios = pd.read_csv(REPO / "reports" / "scenario_analysis" / "scenario_comparison.csv")
    figure_scenarios(scenarios)
    anomalies = pd.read_csv(REPO / "reports" / "anomaly_detection" / "anomalies.csv")
    dq = pd.read_csv(REPO / "reports" / "data_quality" / "data_quality_report.csv")

    cur, lt3, lt7 = (policies.iloc[i] for i in range(3))
    sc = scenarios.set_index("scenario")
    by_year = sales.groupby(sales["full_date"].dt.year)["sales_amount"].sum()
    dataco_last = sales.loc[sales["source_system"] == "dataco", "full_date"].max()
    olist_first = sales.loc[sales["source_system"] == "olist", "full_date"].min()
    anomaly_domains = anomalies["metric"].value_counts()
    values = {
        "total_revenue": aed(kpi["total_revenue"]),
        "gross_margin": aed(kpi["gross_margin"]),
        "gross_margin_pct": pct(kpi["gross_margin_pct"]),
        "total_units": f"{kpi['total_units']:,.0f}",
        "aov": f"AED {kpi['aov']:,.2f}",
        "inventory_value": aed(kpi["inventory_value"]),
        "stockout_rate": pct(kpi["stockout_rate"]),
        "fill_rate": pct(kpi["fill_rate"]),
        "units_demanded": f"{kpi['units_demanded']:,.0f}",
        "units_fulfilled": f"{kpi['units_fulfilled']:,.0f}",
        "units_lost": f"{kpi['units_demanded'] - kpi['units_fulfilled']:,.0f}",
        "supplier_otd": pct(kpi["supplier_otd"]),
        "avg_lead_time": f"{kpi['avg_lead_time']:.1f}",
        "inventory_turnover": f"{kpi['inventory_turnover']:.1f}",
        "sales_rows": f"{len(sales):,}",
        "inventory_rows": f"{len(inv):,}",
        "shipment_rows": f"{len(d['shipments']):,}",
        "date_min": sales["full_date"].min().strftime("%d %b %Y"),
        "date_max": sales["full_date"].max().strftime("%d %b %Y"),
        "dataco_last": dataco_last.strftime("%b %Y"),
        "olist_first": olist_first.strftime("%b %Y"),
        "rev_2016": aed(by_year[2016]),
        "rev_2017": aed(by_year[2017]),
        "rev_2017_growth": pct(by_year[2017] / by_year[2016] - 1),
        "n_categories": str(len(categories)),
        "top_cat": categories.index[0],
        "top_cat_share": pct(categories["share"].iloc[0]),
        "top_cat_margin": pct(categories["margin_pct"].iloc[0]),
        "top3_share": pct(categories["share"].head(3).sum()),
        "cat2": categories.index[1],
        "cat2_margin": pct(categories["margin_pct"].iloc[1]),
        "cat3": categories.index[2],
        "cat3_margin": pct(categories["margin_pct"].iloc[2]),
        "n_products_inv": str(inv["product_key"].nunique()),
        "band_short": pct(bands.iloc[0]["stockout_rate"]),
        "band_mid": pct(bands.iloc[1]["stockout_rate"]),
        "band_long": pct(bands.iloc[2]["stockout_rate"]),
        "band_short_n": str(bands.iloc[0]["products"]),
        "band_mid_n": str(bands.iloc[1]["products"]),
        "band_long_n": str(bands.iloc[2]["products"]),
        "rho": f"{rho:.2f}",
        "cur_stockout": pct(cur["stockout_rate"]),
        "cur_fill": pct(cur["fill_rate"]),
        "cur_inv": aed(cur["avg_inventory_value_aed"]),
        "lt3_stockout": pct(lt3["stockout_rate"]),
        "lt3_fill": pct(lt3["fill_rate"]),
        "lt3_inv": aed(lt3["avg_inventory_value_aed"]),
        "lt3_inv_delta": pct(lt3["avg_inventory_value_aed"] / cur["avg_inventory_value_aed"] - 1),
        "lt3_units_delta": f"{lt3['units_fulfilled'] - cur['units_fulfilled']:,.0f}",
        "lt3_rev_delta": aed(lt3["revenue_fulfilled_aed"] - cur["revenue_fulfilled_aed"]),
        "lt3_inv_abs_delta": aed(lt3["avg_inventory_value_aed"] - cur["avg_inventory_value_aed"]),
        "lt7_stockout": pct(lt7["stockout_rate"]),
        "lt7_fill": pct(lt7["fill_rate"]),
        "lt7_inv": aed(lt7["avg_inventory_value_aed"]),
        "lt7_inv_delta": pct(lt7["avg_inventory_value_aed"] / cur["avg_inventory_value_aed"] - 1),
        "lt7_units_delta": f"{lt7['units_fulfilled'] - lt3['units_fulfilled']:,.0f}",
        "risk_top": risk.iloc[0]["supplier_id"],
        "risk_top_score": f"{risk.iloc[0]['risk_score']:.1f}",
        "risk_second": risk.iloc[1]["supplier_id"],
        "risk_second_score": f"{risk.iloc[1]['risk_score']:.1f}",
        "risk_low": risk.iloc[-1]["supplier_id"].replace("  ", " "),
        "risk_low_score": f"{risk.iloc[-1]['risk_score']:.1f}",
        "n_high_risk": str((risk["risk_level"] == "High").sum()),
        "fc_best": forecast["WAPE"].idxmin(),
        "fc_best_wape": f"{forecast['WAPE'].min():.2f}%",
        "fc_best_cov": pct(forecast.loc[forecast["WAPE"].idxmin(), "interval_coverage"], 0),
        "fc_naive_wape": f"{forecast.loc['Seasonal Naive', 'WAPE']:.2f}%",
        "fc_naive_cov": pct(forecast.loc["Seasonal Naive", "interval_coverage"], 0),
        "fc_worst_wape": f"{forecast['WAPE'].max():.2f}%",
        "fc_ets_cov": pct(forecast.loc["ETS", "interval_coverage"], 0),
        "fc_sarima_cov": pct(forecast.loc["SARIMA", "interval_coverage"], 0),
        "anomaly_high": f"{len(anomalies):,}",
        "anomaly_inv": f"{anomaly_domains.get('inventory_change', 0):,}",
        "anomaly_transport": f"{anomaly_domains.get('transport_cost', 0):,}",
        "anomaly_sales": f"{anomaly_domains.get('daily_sales', 0):,}",
        "sc_base_stockout": pct(sc.loc["Baseline (no change)", "stockout_rate"]),
        "sc_base_rar": aed(sc.loc["Baseline (no change)", "revenue_at_risk_aed"]),
        "sc_d10_stockout": pct(sc.loc["Demand +10%", "stockout_rate"]),
        "sc_d10_rar": aed(sc.loc["Demand +10%", "revenue_at_risk_aed"]),
        "sc_lt50_stockout": pct(sc.loc["Lead time +50% (max)", "stockout_rate"]),
        "sc_lt50_rar": aed(sc.loc["Lead time +50% (max)", "revenue_at_risk_aed"]),
        "sc_lt30_stockout": pct(sc.loc["Lead time -30% (max)", "stockout_rate"], 2),
        "sc_tc40_cost": aed(sc.loc["Transport cost +40% (max)", "projected_transport_cost_aed"]),
        "sc_base_cost": aed(sc.loc["Baseline (no change)", "projected_transport_cost_aed"]),
        "sc_stress_stockout": pct(sc.loc["Combined stress (worst case)", "stockout_rate"]),
        "sc_stress_rar": aed(sc.loc["Combined stress (worst case)", "revenue_at_risk_aed"]),
        "dq_rows": f"{int(dq['rows'].iloc[0]):,}",
        "dq_missing": f"{dq['missing_pct'].iloc[0]:.2f}%",
        "dq_warnings": f"{int(dq['warning_issues'].iloc[0]):,}",
    }
    pdf = render(values)
    print(f"Wrote {pdf.relative_to(REPO)}")
    for k in ("total_revenue", "fill_rate", "stockout_rate", "inventory_turnover"):
        print(f"  {k}: {values[k]}")


if __name__ == "__main__":
    main()
