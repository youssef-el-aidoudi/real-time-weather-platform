#Real-Time Weather Data Platform
> A production-grade data engineering pipeline that collects live weather data for major French cities, stores it in PostgreSQL, transforms it with dbt, orchestrates updates every 5 minutes with Apache Airflow, and serves an interactive Apache Superset dashboard.

---

## 🎯 Project Overview

This project demonstrates a complete, end-to-end **ELT (Extract, Load, Transform)** data pipeline built with industry-standard tools. All weather data is fetched in real time from the **Open-Meteo API** — no simulated or artificial values.

**Business objective**: Monitor current weather conditions for 5 major French cities in near real-time, with historical trends available for analysis.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Environment                   │
│                                                                 │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────┐ │
│  │  Open-Meteo  │───▶│ Python Ingest  │───▶│   PostgreSQL    │ │
│  │  REST API    │    │ insert_records │    │ dev.raw_weather  │ │
│  └──────────────┘    └────────────────┘    └────────┬────────┘ │
│                                                      │          │
│  ┌──────────────────────────────────────────┐        │          │
│  │         Apache Airflow (every 5 min)      │        │          │
│  │  ingest → validate → dbt transform        │        │          │
│  └──────────────────────────────────────────┘        │          │
│                                                      ▼          │
│                                            ┌─────────────────┐ │
│                                            │   dbt models    │ │
│                                            │  stg_weather    │ │
│                                            │  weather_report │ │
│                                            │  daily_average  │ │
│                                            └────────┬────────┘ │
│                                                      │          │
│                                                      ▼          │
│                                            ┌─────────────────┐ │
│                                            │ Apache Superset │ │
│                                            │   Dashboard     │ │
│                                            └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🌊 Data Flow

```
1. Open-Meteo API  →  fetch current weather (temperature, wind speed, WMO code)
2. Python script   →  parse JSON, translate WMO code, deduplicate (city, time)
3. PostgreSQL      →  dev.raw_weather_data  (raw layer — immutable)
4. dbt staging     →  dev.stg_weather_data  (dedup + timezone normalisation)
5. dbt mart        →  dev.weather_report    (BI-ready full observations)
6. dbt mart        →  dev.daily_average     (daily aggregates per city)
7. Apache Superset →  France Live Weather dashboard (7 charts, auto-refresh 60s)
```

---

## 🛠️ Technologies

| Layer | Tool | Version | Role |
|---|---|---|---|
| **Orchestration** | Apache Airflow | 3.0.0 | Schedule DAG every 5 min |
| **Ingestion** | Python + requests | 3.12 | Call Open-Meteo API |
| **Storage** | PostgreSQL | 14.17 | Raw + transformed data |
| **Transformation** | dbt-postgres | 1.9 | Staging + mart models |
| **Visualization** | Apache Superset | 3.0.0 | Interactive dashboard |
| **Cache/Broker** | Redis | 7 | Superset cache |
| **Container** | Docker Compose | v2 | Local orchestration |

---

## 📁 Project Structure

```
.
├── config/
│   └── cities.json              # ← Add/remove cities HERE (single source of truth)
├── scripts/
│   ├── api_request.py           # Open-Meteo HTTP client (retries, logging)
│   ├── cities.py                # City config loader
│   ├── insert_records.py        # Ingest: API → PostgreSQL raw
│   ├── seed_weather.py          # Historical seed (last 24h, run once)
│   └── validate_data.py         # Post-ingest data quality checks
├── airflow/
│   └── dags/
│       └── orchestrator.py      # DAG: ingest → validate → dbt
├── dbt/
│   └── my_project/
│       └── models/
│           ├── sources/sources.yml
│           ├── staging/
│           │   ├── stg_weather_data.sql
│           │   └── schema.yml   # dbt tests + docs
│           └── mart/
│               ├── weather_report.sql
│               ├── daily_average.sql
│               └── schema.yml   # dbt tests + docs
├── docker/
│   ├── dashboard/               # Superset export (databases, datasets, charts, dashboards)
│   ├── docker-init.sh           # Superset initialisation
│   ├── import_dashboard.py      # Import France Live Weather dashboard
│   └── sync_dashboard.py        # Sync chart definitions
├── postgres/
│   ├── airflow_init.sql         # Create airflow DB + user
│   └── superset_init.sql        # Create superset DB + user
├── tests/
│   ├── test_api_request.py      # HTTP client unit tests
│   ├── test_cities.py           # City loader unit tests
│   └── test_weather_descriptions.py  # WMO code tests
├── .github/workflows/ci.yml     # GitHub Actions: tests + lint
├── .env.example                 # Environment variable template
├── docker-compose.yml           # Full stack definition
└── requirements.txt
```

---

## 🌍 Cities Configuration

Cities are defined in a single file: [`config/cities.json`](config/cities.json)

| City | Country | Latitude | Longitude |
|---|---|---|---|
| Paris | France | 48.8566 | 2.3522 |
| Lyon | France | 45.7640 | 4.8357 |
| Marseille | France | 43.2965 | 5.3698 |
| Toulouse | France | 43.6047 | 1.4442 |
| Dijon | France | 47.3220 | 5.0415 |

### ➕ How to Add a New City

1. Edit `config/cities.json` and add:
```json
{
  "city": "Bordeaux",
  "country": "France",
  "latitude": 44.8378,
  "longitude": -0.5792,
  "timezone": "Europe/Paris",
  "active": true
}
```
2. Restart the pipeline — no other file needs to change.

### ➖ How to Disable a City

Set `"active": false` in `config/cities.json`.

---

## 📡 Open-Meteo API

**Endpoint**: `https://api.open-meteo.com/v1/forecast`

**Parameters used**:

| Parameter | Value | Description |
|---|---|---|
| `latitude` / `longitude` | from cities.json | City coordinates |
| `current` | `temperature_2m,weather_code,wind_speed_10m` | Current conditions |
| `timezone` | `auto` | Local time resolution |

**Variables returned**:
- `temperature_2m` — Air temperature at 2m above ground (°C)
- `wind_speed_10m` — Wind speed at 10m above ground (km/h)
- `weather_code` — WMO weather interpretation code (0–99)

**Error handling**: 3 retries with exponential backoff (2s, 4s, 8s). Raises on final failure.

---

## 🗄️ Data Model

```
dev.raw_weather_data          ← Raw, immutable, insert-only
├── id                SERIAL PRIMARY KEY
├── city              TEXT NOT NULL
├── temperature       FLOAT NOT NULL
├── weather_description TEXT NOT NULL
├── wind_speed        FLOAT NOT NULL
├── time              TIMESTAMP NOT NULL      ← observation time (local)
├── inserted_at       TIMESTAMP DEFAULT NOW() ← ingestion time
└── utc_offset        TEXT NOT NULL

dev.stg_weather_data          ← Cleaned, deduplicated (dbt staging)
├── id                         ← from raw
├── city
├── temperature
├── weather_description
├── wind_speed
├── weather_time_local         ← renamed from 'time'
└── inserted_at_local

dev.weather_report             ← BI-ready mart (dbt)
└── (same columns as stg)      ← direct projection, source of most charts

dev.daily_average              ← Daily aggregates (dbt)
├── city
├── date
├── avg_temperature
└── avg_wind_speed
```

**Deduplication strategy** (two-layer):
1. **Python (insert)**: `INSERT ... WHERE NOT EXISTS (SELECT 1 WHERE city = %s AND time = %s)`
2. **dbt (staging)**: `ROW_NUMBER() OVER (PARTITION BY city, time ORDER BY inserted_at) = 1`

Both layers are intentional. The Python layer prevents duplicate rows at the raw level. The dbt layer provides an additional safety net during transformation.

---

## ⚙️ Airflow Orchestration

**DAG**: `weather_pipeline` | **Schedule**: every 5 minutes | **No catchup**

```
ingest_weather_data
      │  (PythonOperator — calls insert_records.main())
      ▼
validate_data_quality
      │  (PythonOperator — checks coverage + NULL values)
      ▼
run_dbt_transformations
      │  (DockerOperator — runs dbt inside ephemeral container)
      ▼
      ✓
```

**Reliability settings**: `retries=3`, `retry_exponential_backoff=True`, `retry_delay=1min`

Access: http://localhost:8000 | Login: `admin` / `<see docker logs airflow_container>`

---

## 🔄 dbt Transformations

**3 models**, **PASS=3**, **~0.4s** total execution time.

| Model | Layer | Materialization | Description |
|---|---|---|---|
| `stg_weather_data` | Staging | table | Dedup + rename columns |
| `weather_report` | Mart | table | Full BI-ready observations |
| `daily_average` | Mart | table | Daily AVG per city |

**Tests** (run with `dbt test`):
- `not_null` on all critical columns
- `unique` on `id` in stg and weather_report
- Source-level `not_null` on raw_weather_data

---

## 📊 Superset Dashboard

**Dashboard**: France Live Weather | http://localhost:8088 | Login: `admin` / `admin`

| Chart | Type | Dataset | Description |
|---|---|---|---|
| Current Average Temperature | Big Number | weather_report | Latest avg temp across all cities |
| Current Average Wind Speed | Big Number | weather_report | Latest avg wind across all cities |
| 24h Temperature Trend | Line chart | weather_report | Hourly temp per city (last 24h) |
| Temperature by City | Bar chart | weather_report | Current temp comparison |
| Weather Conditions | Pie chart | weather_report | WMO condition distribution |
| Daily Average Temperature | Bar chart | daily_average | Daily avg temp per city (last 7d) |
| Live Weather Observations | Table | weather_report | All observations with details |

---

## ✅ Data Quality

Checks performed automatically after each ingestion (Airflow task `validate_data_quality`):

1. **Coverage**: All active cities must have data inserted in the last 10 minutes
2. **NULL check**: `city`, `temperature`, `wind_speed`, `time`, `weather_description` must not be NULL in recent rows
3. **dbt tests**: `not_null`, `unique` on all model columns (run via `dbt test`)

---

## 🔒 Security Notes

- Credentials for **local development** are hardcoded in `docker-compose.yml` and `docker/.env`
- **Never commit real credentials** to a public repository
- Copy `.env.example` to `.env` and customize before any non-local deployment
- The `SUPERSET_SECRET_KEY` in `docker/.env` must be changed to a secure random key in production
- The Docker socket mount (`/var/run/docker.sock`) in Airflow is required for the `DockerOperator` to spawn dbt containers; it is a known security trade-off in local/dev environments

---

## 🚀 Getting Started

### Prerequisites

- Docker Desktop (v24+) running
- Docker Compose v2
- 6 GB RAM allocated to Docker (for Airflow + Superset)

### Start the Full Stack

```bash
git clone <repo-url>
cd Real-time-weather-main
docker compose up -d
```

**First startup** (~5 min): Docker will pull images, seed 24h of historical data, run dbt, and initialize Superset.

### Check Status

```bash
docker compose ps
```

Expected output: `db (healthy)`, `airflow`, `redis`, `superset (healthy)` all `Up`.

### Access

| Service | URL | Credentials |
|---|---|---|
| Superset Dashboard | http://localhost:8088 | admin / admin |
| Airflow | http://localhost:8000 | admin / *see logs* |
| PostgreSQL | localhost:5000 | db_user / db_password |

```bash
# Get Airflow password
docker logs airflow_container 2>&1 | grep "Password for user"
```

### Run Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Run dbt Tests

```bash
docker compose run --rm dbt test
```

### Stop

```bash
docker compose down          # keep data volumes
docker compose down -v       # destroy all data (clean slate)
```

---

## 🔧 Technical Challenges & Solutions

| Challenge | Solution |
|---|---|
| PostgreSQL healthcheck race condition (weather-init connects before init scripts finish) | Connection retry loop with 15 attempts × 3s delay in `seed_weather.py` + `start_period: 15s` in healthcheck |
| Airflow `DockerOperator` needs Docker access | Mount `/var/run/docker.sock` (accepted security trade-off in dev) |
| dbt running inside Airflow without embedding dbt as a Python library | Ephemeral container via `DockerOperator` — clean separation of concerns |
| Superset YAML import with chart sync | Two-phase init: `import-dashboards` CLI + `sync_dashboard.py` for params |
| Duplicate observations on retries / re-runs | Dual deduplication: Python `WHERE NOT EXISTS` + dbt `ROW_NUMBER()` |

---

## 🚀 Possible Future Improvements

- [ ] Add more French cities (edit `config/cities.json` only)
- [ ] Switch dbt materialization to `incremental` for performance at scale
- [ ] Add weather forecast data (Open-Meteo supports 7-day forecasts)
- [ ] Replace Docker socket mount with Celery executor + KubernetesExecutor
- [ ] Add Prometheus metrics + Grafana for pipeline monitoring
- [ ] Deploy on a cloud VM with GitHub Actions CD
- [ ] Add Great Expectations for advanced data quality rules

---

## 👤 Author

Master 2 BDIA — Data Engineering Portfolio Project  
Technologies: Python · PostgreSQL · dbt · Apache Airflow · Apache Superset · Docker
