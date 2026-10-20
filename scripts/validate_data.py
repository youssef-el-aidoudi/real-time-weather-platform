"""
Post-ingestion data quality check.
Called as Airflow PythonOperator after ingest_weather_data.

Verifies:
  - Recent data exists for every active city (last 30 minutes)
  - No NULL values on critical columns in recent rows
  - All cities produced at least one row in the last cycle

Raises RuntimeError if any check fails (marks the task as FAILED in Airflow).
"""
import logging
import os

import psycopg2

from cities import get_locations

logger = logging.getLogger(__name__)


def _get_conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "db"),
        user=os.getenv("POSTGRES_USER", "db_user"),
        password=os.getenv("POSTGRES_PASSWORD", "db_password"),
    )


def validate() -> None:
    """Run data-quality checks. Raises RuntimeError on failure."""
    expected_cities = {city for city, _, _ in get_locations()}
    logger.info("Running data quality checks for cities: %s", expected_cities)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:

            # -- 1. Recent coverage per city (last 30 minutes) ----------------
            # Window is 30 min (covers 6 x 5-min Airflow cycles) because
            # Open-Meteo updates its `current` field every ~15 min, so the
            # Python dedup guard may legitimately skip inserts for several runs.
            cur.execute("""
                SELECT city, COUNT(*) AS cnt, MAX(inserted_at) AS latest_insert
                FROM   dev.raw_weather_data
                WHERE  inserted_at >= NOW() - INTERVAL '30 minutes'
                GROUP  BY city
            """)
            rows = cur.fetchall()
            found_cities = set()
            for city, cnt, latest in rows:
                found_cities.add(city)
                logger.info(
                    "[OK] %-12s | %d row(s) | latest insert: %s",
                    city, cnt, latest,
                )

            missing = expected_cities - found_cities
            if missing:
                raise RuntimeError(
                    f"No recent data (last 30 min) found for: {missing}. "
                    "Possible causes: API unavailable, deduplication, or ingest failure."
                )

            # -- 2. NULL check on critical columns ----------------------------
            cur.execute("""
                SELECT COUNT(*)
                FROM   dev.raw_weather_data
                WHERE  inserted_at >= NOW() - INTERVAL '30 minutes'
                  AND  (city IS NULL OR temperature IS NULL OR wind_speed IS NULL
                        OR time IS NULL OR weather_description IS NULL)
            """)
            null_count = cur.fetchone()[0]
            if null_count > 0:
                raise RuntimeError(
                    f"Found {null_count} row(s) with NULL critical values in the last 30 minutes."
                )

            logger.info("[OK] All data-quality checks passed")

    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    validate()
