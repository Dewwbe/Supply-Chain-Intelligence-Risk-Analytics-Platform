"""The one PySpark entrypoint in this codebase (README.md §4).

Does the actual "large join" — Olist's 4-way join across orders,
order_items, products and customers (~113k order-item rows fanned out
against three other tables) — in Spark rather than pandas, then unions the
result with DataCo (already at line-item grain, no heavy join needed) into
one sales-lines table. `join_olist` mirrors `olist_transform.join_sources`
column-for-column; both feed the same `finalize_sales_lines` so
standardization logic is never duplicated between the pandas and Spark
paths.

Note (Windows local dev): PySpark's local file access needs `winutils.exe`/
`HADOOP_HOME` set up on Windows; this runs unmodified in the Docker image
and CI (Linux), see Dockerfile.
"""

from __future__ import annotations

import pandas as pd
from etl.extract import dataco, olist
from etl.transform import dataco_transform, olist_transform
from etl.transform.dates import parse_dates
from pyspark.sql import SparkSession
from src.common.logging import get_logger

logger = get_logger(__name__)


def get_spark_session() -> SparkSession:
    """A local SparkSession sized for this project's data volume (hundreds of thousands of rows)."""
    return (
        SparkSession.builder.appName("gulfmart-etl")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def join_olist(spark: SparkSession, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Perform the Olist orders+order_items+products+customers join in Spark.

    `frames` is the dict returned by `etl.extract.olist.run()`. Returns the
    joined result as pandas (small enough post-join to collect on the
    driver at this project's scale) for `olist_transform.finalize_sales_lines`.
    """
    products = olist_transform.translate_categories(
        frames["products"], frames["category_translation"]
    )

    orders_sdf = spark.createDataFrame(frames["orders"])
    items_sdf = spark.createDataFrame(frames["order_items"])
    products_sdf = spark.createDataFrame(products)
    customers_sdf = spark.createDataFrame(frames["customers"])

    joined = (
        items_sdf.join(orders_sdf, on="order_id", how="inner")
        .join(products_sdf, on="product_id", how="left")
        .join(customers_sdf, on="customer_id", how="left")
    )

    result = joined.toPandas()
    return parse_dates(
        result,
        [
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )


def run(
    olist_frames: dict[str, pd.DataFrame] | None = None,
    dataco_frames: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Build the unified Olist+DataCo sales-lines table. Matches the DAG's `spark_transform.run()` import.

    Accepts already-extracted frames (that's what `etl/run_local.py` passes,
    to avoid re-reading the CSVs); re-extracts itself otherwise.
    """
    olist_frames = olist_frames or olist.run()
    dataco_frames = dataco_frames or dataco.run()

    spark = get_spark_session()
    try:
        joined_olist = join_olist(spark, olist_frames)
        olist_lines = olist_transform.finalize_sales_lines(joined_olist)
        dataco_lines = dataco_transform.build_sales_lines(dataco_frames["shipments"])

        unified = pd.concat([olist_lines, dataco_lines], ignore_index=True)
        logger.info(
            "spark_transform_done",
            olist_rows=len(olist_lines),
            dataco_rows=len(dataco_lines),
            total_rows=len(unified),
        )
        return unified
    finally:
        spark.stop()
