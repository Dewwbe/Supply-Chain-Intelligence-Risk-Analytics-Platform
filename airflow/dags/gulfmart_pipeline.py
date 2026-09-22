"""Daily orchestration DAG for the GulfMart supply chain pipeline.

extract -> validate -> transform (pandas + spark) -> load -> quality report -> KPIs
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "gulfmart-data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="gulfmart_pipeline",
    description="Extract, validate, transform and load GulfMart supply chain data",
    default_args=default_args,
    schedule="0 2 * * *",  # daily at 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["gulfmart", "etl"],
) as dag:

    def extract_sources(**_):
        from etl.extract import dataco, olist, uae_open_data

        olist.run()
        dataco.run()
        uae_open_data.run()

    def validate_sources(**_):
        from etl.validate import run_all_checks

        run_all_checks()

    def spark_transform(**_):
        from etl.transform.spark_transform import run

        run()

    def load_warehouse(**_):
        from etl.load import run as load_run

        load_run()

    def run_quality_report(**_):
        from etl.validate import generate_quality_report

        generate_quality_report()

    extract = PythonOperator(task_id="extract_sources", python_callable=extract_sources)
    validate = PythonOperator(task_id="validate_sources", python_callable=validate_sources)
    transform = PythonOperator(task_id="spark_transform", python_callable=spark_transform)
    load = PythonOperator(task_id="load_warehouse", python_callable=load_warehouse)
    quality_report = PythonOperator(task_id="quality_report", python_callable=run_quality_report)

    extract >> validate >> transform >> load >> quality_report
