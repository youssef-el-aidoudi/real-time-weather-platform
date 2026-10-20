"""
Historical seed: loads the last 24 hours of hourly weather data for all active
cities so the dashboard is immediately useful on first startup.

This script runs once (via Docker Compose `weather-init` service).
It includes a connection-retry loop to handle the race condition where
PostgreSQL reports healthy but is still finishing init scripts.
"""
import logging
import time
from datetime import datetime
from urllib.parse import urlencode

import psycopg2

from api_request import fetch_data
from cities import get_locations
from insert_records import WEATHER_DESCRIPTIONS, connect_to_db, create_table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Robust connection (retries on "Connection refused" — Docker race condition)
# ---------------------------------------------------------------------------

def connect_with_retry(
    max_attempts: int = 15, delay: float = 3.0
) -> psycopg2.extensions.connection:
    """
    Try to connect to PostgreSQL up to max_attempts times.

    Rationale: pg_isready (used in Docker healthcheck) can return OK while
    PostgreSQL is still executing init SQL scripts, causing a brief window
    where TCP connections are refused.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return connect_to_db()
        except psycopg2.OperationalError as exc:
            logger.warning(
                "DB connection attempt %d/%d failed: %s", attempt, max_attempts, exc
            )
            if attempt < max_attempts:
                logger.info("Retrying in %.0fs ...", delay)
                time.sleep(delay)
    raise RuntimeError(f"Could not connect to PostgreSQL after {max_attempts} attempts")


# ---------------------------------------------------------------------------
# Seed one city
# ---------------------------------------------------------------------------

def seed_location(
    conn: psycopg2.extensions.connection,
    city: str,
    latitude: float,
    longitude: float,
) -> None:
    """Fetch last 24 h of hourly data and bulk-insert with dedup guard."""
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,weather_code,wind_speed_10m",
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "past_days": 1,
        "forecast_days": 1,
        "timezone": "auto",
    })
    data = fetch_data(f"https://api.open-meteo.com/v1/forecast?{query}")

    hourly = data["hourly"]
    utc_offset = str(data.get("utc_offset_seconds", 0) / 3600)
    now = datetime.fromisoformat(data["current"]["time"])

    rows = []
    for timestamp, temperature, code, wind_speed in zip(
        hourly["time"],
        hourly["temperature_2m"],
        hourly["weather_code"],
        hourly["wind_speed_10m"],
    ):
        if datetime.fromisoformat(timestamp) <= now:
            rows.append((
                city,
                temperature,
                WEATHER_DESCRIPTIONS.get(code, f"WMO code {code}"),
                wind_speed,
                timestamp,
                utc_offset,
            ))

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO dev.raw_weather_data
                (city, temperature, weather_description, wind_speed, time, inserted_at, utc_offset)
            SELECT %s, %s, %s, %s, %s, NOW(), %s
            WHERE NOT EXISTS (
                SELECT 1 FROM dev.raw_weather_data WHERE city = %s AND time = %s
            );
            """,
            [row + (row[0], row[4]) for row in rows],
        )
    conn.commit()
    logger.info("Seeded %d hourly observations for %s", len(rows), city)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    locations = get_locations()
    logger.info(
        "Starting historical seed for %d cities: %s",
        len(locations),
        [c for c, _, _ in locations],
    )
    conn = connect_with_retry()
    try:
        create_table(conn)
        for city, lat, lon in locations:
            seed_location(conn, city, lat, lon)
        logger.info("Historical seed completed successfully")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
