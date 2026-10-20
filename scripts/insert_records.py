"""
Weather data ingestion: Open-Meteo API -> PostgreSQL raw layer.

Responsibilities:
  - Connect to PostgreSQL (with env-var driven config)
  - Ensure the raw table exists (idempotent DDL)
  - For each active city: call Open-Meteo, parse JSON, insert with dedup guard
  - Log inserted vs. skipped (duplicate) counts
"""
import logging
import os
from urllib.parse import urlencode

import psycopg2

from api_request import fetch_data
from cities import get_locations

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WMO weather-code translation table (source: open-meteo.com/en/docs)
# ---------------------------------------------------------------------------
WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def connect_to_db() -> psycopg2.extensions.connection:
    """Establish a psycopg2 connection from environment variables."""
    host = os.getenv("POSTGRES_HOST", "db")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    dbname = os.getenv("POSTGRES_DB", "db")
    user = os.getenv("POSTGRES_USER", "db_user")
    password = os.getenv("POSTGRES_PASSWORD", "db_password")
    logger.info("Connecting to PostgreSQL at %s:%d/%s as %s", host, port, dbname, user)
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        logger.info("PostgreSQL connection established")
        return conn
    except Exception as exc:
        logger.error("Failed to connect to PostgreSQL: %s", exc)
        raise


def create_table(conn: psycopg2.extensions.connection) -> None:
    """Create schema and raw table if they do not exist (idempotent)."""
    logger.info("Ensuring dev.raw_weather_data table exists")
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS dev;

            CREATE TABLE IF NOT EXISTS dev.raw_weather_data (
                id                   SERIAL PRIMARY KEY,
                city                 TEXT        NOT NULL,
                temperature          FLOAT       NOT NULL,
                weather_description  TEXT        NOT NULL,
                wind_speed           FLOAT       NOT NULL,
                time                 TIMESTAMP   NOT NULL,
                inserted_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
                utc_offset           TEXT        NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_raw_city_time
                ON dev.raw_weather_data (city, time);
        """)
        conn.commit()
    logger.info("Table ready")


def insert_record(
    conn: psycopg2.extensions.connection, data: dict, city: str
) -> bool:
    """
    Insert one weather observation.

    Deduplication: (city, time) pair must be unique.
    Uses INSERT ... WHERE NOT EXISTS so duplicate rows are silently skipped.

    Returns:
        True  - row was inserted.
        False - row already existed (duplicate skipped).
    """
    current = data["current"]
    weather_code = current["weather_code"]
    description = WEATHER_DESCRIPTIONS.get(weather_code, f"WMO code {weather_code}")
    utc_offset = str(data.get("utc_offset_seconds", 0) / 3600)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dev.raw_weather_data
                (city, temperature, weather_description, wind_speed, time, inserted_at, utc_offset)
            SELECT %s, %s, %s, %s, %s, NOW(), %s
            WHERE NOT EXISTS (
                SELECT 1 FROM dev.raw_weather_data WHERE city = %s AND time = %s
            );
            """,
            (
                city,
                current["temperature_2m"],
                description,
                current["wind_speed_10m"],
                current["time"],
                utc_offset,
                city,
                current["time"],
            ),
        )
        inserted = cur.rowcount > 0
        conn.commit()

    if inserted:
        logger.info(
            "[OK] %s | %.1f C | %s | %.1f km/h | %s",
            city,
            current["temperature_2m"],
            description,
            current["wind_speed_10m"],
            current["time"],
        )
    else:
        logger.debug("[SKIP] %s @ %s -- duplicate skipped", city, current["time"])

    return inserted


# ---------------------------------------------------------------------------
# Main entry point (called by Airflow PythonOperator)
# ---------------------------------------------------------------------------

def main() -> None:
    """Ingest current weather for all active cities."""
    locations = get_locations()
    logger.info(
        "Starting ingestion for %d cities: %s",
        len(locations),
        [c for c, _, _ in locations],
    )

    conn = connect_to_db()
    try:
        create_table(conn)
        inserted_total = 0
        skipped_total = 0

        for city, latitude, longitude in locations:
            query = urlencode({
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            })
            url = f"https://api.open-meteo.com/v1/forecast?{query}"
            data = fetch_data(url)
            ok = insert_record(conn, data, city)
            if ok:
                inserted_total += 1
            else:
                skipped_total += 1

        logger.info(
            "Ingestion complete -- inserted: %d, duplicates skipped: %d",
            inserted_total,
            skipped_total,
        )
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        raise
    finally:
        conn.close()
        logger.info("PostgreSQL connection closed")


if __name__ == "__main__":
    main()
