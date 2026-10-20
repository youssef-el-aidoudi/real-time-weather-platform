"""
DAG: weather_pipeline
=====================
Real-time weather data pipeline for French cities.

Schedule : every 5 minutes
Timezone : UTC

Pipeline graph:
  ingest_weather_data
        |
  validate_data_quality
        |
  run_dbt_transformations
"""
import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

sys.path.append("/opt/airflow/scripts")

from insert_records import main as _ingest
from validate_data import validate as _validate

log = logging.getLogger(__name__)

# -- Environment (injected by docker-compose) ---------------------------------
HOST_PROJECT_DIR = os.environ.get("HOST_PROJECT_DIR", "")
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "real-time-weather-main_my-network")

if not HOST_PROJECT_DIR:
    log.warning(
        "HOST_PROJECT_DIR is not set. DockerOperator mounts will fail. "
        "Set HOST_PROJECT_DIR in docker-compose.yml or .env."
    )

# -- Default args -------------------------------------------------------------
default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "email_on_failure": False,
    "email_on_retry": False,
}

# -- DAG definition -----------------------------------------------------------
dag = DAG(
    dag_id="weather_pipeline",
    description="Real-time weather pipeline: Open-Meteo -> PostgreSQL -> dbt -> Superset",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=timedelta(minutes=5),
    catchup=False,
    tags=["weather", "france", "real-time", "dbt"],
)

with dag:

    # -- Task 1 : Ingest ------------------------------------------------------
    ingest_weather_data = PythonOperator(
        task_id="ingest_weather_data",
        python_callable=_ingest,
        doc_md="""
        ### Ingest weather data
        Calls Open-Meteo API for each active French city and inserts the current
        observation into `dev.raw_weather_data`.
        Deduplication: `(city, time)` pair must be unique — duplicates are silently skipped.
        """,
    )

    # -- Task 2 : Validate ----------------------------------------------------
    validate_data_quality = PythonOperator(
        task_id="validate_data_quality",
        python_callable=_validate,
        doc_md="""
        ### Validate data quality
        Checks that:
        - Every active city produced at least one row in the last 30 minutes.
        - No NULL values on critical columns (city, temperature, wind_speed, time).
        Raises RuntimeError on failure -> marks the DAG run as FAILED.
        """,
    )

    # -- Task 3 : Transform (dbt) ---------------------------------------------
    run_dbt_transformations = DockerOperator(
        task_id="run_dbt_transformations",
        image="ghcr.io/dbt-labs/dbt-postgres:1.9.latest",
        command="run",
        working_dir="/usr/app",
        mounts=[
            Mount(
                source=f"{HOST_PROJECT_DIR}/dbt/my_project",
                target="/usr/app",
                type="bind",
            ),
            Mount(
                source=f"{HOST_PROJECT_DIR}/dbt/profiles.yml",
                target="/root/.dbt/profiles.yml",
                type="bind",
            ),
        ],
        network_mode=DOCKER_NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="force",
        doc_md="""
        ### Run dbt transformations
        Executes `dbt run` inside an ephemeral container:
        - `stg_weather_data`  - deduplication + timezone normalisation
        - `weather_report`    - mart (full observations, BI-ready)
        - `daily_average`     - mart (daily AVG per city)
        """,
    )

    # -- Dependencies ---------------------------------------------------------
    ingest_weather_data >> validate_data_quality >> run_dbt_transformations
