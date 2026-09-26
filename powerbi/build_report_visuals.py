"""Generates the visuals for all 5 report pages (PBIR visual.json files).

Implements powerbi/report_pages_spec.md. Output matches the visualContainer
format Power BI Desktop itself saves, so the report opens with every page
already built. Re-running replaces every page's visuals.

Run with Power BI Desktop closed, then open GulfMart Supply Chain.pbip.
"""

import hashlib
import json
import shutil
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "GulfMart Supply Chain.Report" / "definition" / "pages"
SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "visualContainer/2.12.0/schema.json"
)

EXECUTIVE = "a1b2c3d4e5f6a7b8c9d0"
SALES = "b2c3d4e5f6a7b8c9d0e1"
INVENTORY = "c3d4e5f6a7b8c9d0e1f2"
SUPPLIER = "d4e5f6a7b8c9d0e1f2a3"
SCENARIO = "e5f6a7b8c9d0e1f2a3b4"


def measure(name: str) -> dict:
    return {"kind": "Measure", "entity": "_Measures", "prop": name}


def column(entity: str, prop: str) -> dict:
    return {"kind": "Column", "entity": entity, "prop": prop}


def _field(f: dict) -> dict:
    return {
        f["kind"]: {"Expression": {"SourceRef": {"Entity": f["entity"]}}, "Property": f["prop"]}
    }


def _projection(f: dict) -> dict:
    return {
        "field": _field(f),
        "queryRef": f"{f['entity']}.{f['prop']}",
        "nativeQueryRef": f["prop"],
    }


def _literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def visual(
    page: str,
    index: int,
    visual_type: str,
    roles: dict[str, list[dict]],
    x: int,
    y: int,
    w: int,
    h: int,
    sort: tuple[dict, str] | None = None,
    objects: dict | None = None,
) -> dict:
    name = hashlib.sha1(f"{page}-{index}".encode()).hexdigest()[:20]
    query: dict = {
        "queryState": {
            role: {"projections": [_projection(f) for f in fields]}
            for role, fields in roles.items()
        }
    }
    if sort:
        query["sortDefinition"] = {
            "sort": [{"field": _field(sort[0]), "direction": sort[1]}],
            "isDefaultSort": True,
        }
    body: dict = {"visualType": visual_type, "query": query}
    if objects:
        body["objects"] = objects
    body["drillFilterOtherVisuals"] = True
    return {
        "$schema": SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": index, "height": h, "width": w, "tabOrder": index},
        "visual": body,
    }


def cards(
    page: str, start: int, names: list[str], x: int, y: int, w: int, h: int, gap: int = 20
) -> list[dict]:
    return [
        visual(page, start + i, "cardVisual", {"Data": [measure(n)]}, x + i * (w + gap), y, w, h)
        for i, n in enumerate(names)
    ]


def slicer(
    page: str, index: int, f: dict, x: int, y: int, w: int, h: int, single_value: bool = False
) -> dict:
    objects = {"data": [{"properties": {"mode": _literal("'Single'")}}]} if single_value else None
    return visual(page, index, "slicer", {"Values": [f]}, x, y, w, h, objects=objects)


def executive_overview() -> list[dict]:
    p = EXECUTIVE
    year, month = column("dim_date", "year"), column("dim_date", "month")
    return [
        *cards(
            p,
            0,
            ["Total Revenue", "Gross Margin", "Inventory Turnover", "Revenue YoY %"],
            320,
            20,
            380,
            180,
        ),
        slicer(p, 4, year, 20, 20, 280, 400),
        visual(
            p,
            5,
            "lineChart",
            {
                "Category": [year, month],
                "Y": [measure("Total Revenue"), measure("Total Revenue PY (SPLY)")],
            },
            320,
            220,
            1580,
            420,
            sort=(year, "Ascending"),
        ),
        visual(
            p,
            6,
            "clusteredBarChart",
            {
                "Category": [column("dim_product", "category")],
                "Y": [measure("Revenue % of All Categories")],
            },
            320,
            660,
            1580,
            400,
            sort=(measure("Revenue % of All Categories"), "Descending"),
        ),
    ]


def sales_demand() -> list[dict]:
    p = SALES
    return [
        *cards(p, 0, ["Total Units Sold", "Average Order Value", "Return Rate"], 320, 20, 510, 180),
        slicer(p, 3, column("dim_location", "emirate"), 20, 20, 280, 400),
        visual(
            p,
            4,
            "lineChart",
            {"Category": [column("dim_date", "full_date")], "Y": [measure("Total Units Sold")]},
            320,
            220,
            1580,
            400,
            sort=(column("dim_date", "full_date"), "Ascending"),
        ),
        visual(
            p,
            5,
            "tableEx",
            {
                "Values": [
                    column("dim_product", "category"),
                    column("dim_product", "subcategory"),
                    measure("Total Revenue"),
                    measure("Total Units Sold"),
                    measure("Average Order Value"),
                ]
            },
            320,
            640,
            1580,
            420,
            sort=(measure("Total Revenue"), "Descending"),
        ),
    ]


def inventory() -> list[dict]:
    p = INVENTORY
    warehouse = column("dim_warehouse", "warehouse_name")
    return [
        *cards(
            p,
            0,
            ["Inventory Value", "Stockout Rate", "Fill Rate", "Inventory Turnover"],
            20,
            20,
            455,
            180,
        ),
        visual(
            p,
            4,
            "tableEx",
            {
                "Values": [
                    column("dim_product", "product_name"),
                    warehouse,
                    measure("Inventory Value"),
                    measure("Stockout Rate"),
                    measure("Fill Rate"),
                ]
            },
            20,
            220,
            1100,
            840,
            sort=(measure("Inventory Value"), "Descending"),
        ),
        visual(
            p,
            5,
            "clusteredBarChart",
            {"Category": [warehouse], "Y": [measure("Stockout Rate")]},
            1140,
            220,
            760,
            840,
            sort=(measure("Stockout Rate"), "Descending"),
        ),
    ]


def supplier_logistics() -> list[dict]:
    p = SUPPLIER
    supplier = column("dim_supplier", "supplier_name")
    return [
        *cards(
            p,
            0,
            ["Average Lead Time", "Supplier OTD", "Transport Cost", "Cancellation Rate"],
            20,
            20,
            455,
            180,
        ),
        visual(
            p,
            4,
            "tableEx",
            {
                "Values": [
                    supplier,
                    measure("Average Lead Time"),
                    measure("Lead-Time Std Dev"),
                    measure("Supplier OTD"),
                    measure("Cost Variability"),
                    measure("Supplier Risk Score"),
                    measure("Supplier Risk Level"),
                ]
            },
            20,
            220,
            1880,
            400,
            sort=(measure("Supplier Risk Score"), "Descending"),
        ),
        visual(
            p,
            5,
            "scatterChart",
            {
                "Category": [supplier],
                "X": [measure("Average Lead Time")],
                "Y": [measure("Supplier Risk Score")],
            },
            20,
            640,
            930,
            420,
        ),
        visual(
            p,
            6,
            "clusteredBarChart",
            {
                "Category": [column("dim_transport", "carrier_name")],
                "Y": [measure("Transport Cost")],
            },
            970,
            640,
            930,
            420,
            sort=(measure("Transport Cost"), "Descending"),
        ),
    ]


def scenario_simulator() -> list[dict]:
    p = SCENARIO
    params = [
        "Demand Change Parameter",
        "Lead Time Change Parameter",
        "Transport Cost Change Parameter",
    ]
    baseline = [
        "Baseline Inventory Value",
        "Baseline Transport Cost",
        "Baseline Stockout Rate",
        "Baseline Revenue",
    ]
    scenario = [
        "Scenario Projected Inventory Value",
        "Scenario Projected Transport Cost",
        "Scenario Stockout Rate",
        "Revenue at Risk",
    ]
    visuals = [
        slicer(p, i, column(t, t), 20, 20 + i * 200, 380, 180, single_value=True)
        for i, t in enumerate(params)
    ]
    visuals += cards(
        p, 3, ["Scenario Stockout Rate", "Scenario Fill Rate", "Revenue at Risk"], 420, 20, 480, 200
    )
    for row, (b, s) in enumerate(zip(baseline, scenario, strict=True)):
        y = 250 + row * 205
        visuals += cards(p, 6 + row * 2, [b, s], 420, y, 730, 185)
    return visuals


def main() -> None:
    builders = {
        EXECUTIVE: executive_overview,
        SALES: sales_demand,
        INVENTORY: inventory,
        SUPPLIER: supplier_logistics,
        SCENARIO: scenario_simulator,
    }
    for page, build in builders.items():
        visuals_dir = PAGES_DIR / page / "visuals"
        if visuals_dir.exists():
            shutil.rmtree(visuals_dir)
        for v in build():
            target = visuals_dir / v["name"] / "visual.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(v, indent=2), encoding="utf-8")
        print(f"{page}: {len(list(visuals_dir.iterdir()))} visuals")


if __name__ == "__main__":
    main()
