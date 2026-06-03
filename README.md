# Slovenia Radar Precipitation Service

A Dockerized service that continuously ingests the [ARSO](https://meteo.arso.gov.si)
Slovenia weather-radar image, decodes it into precipitation (mm/h), and stores a
queryable history in **TimescaleDB**. It exposes a documented **HTTP API** (with Swagger
UI) and a **map GUI** where you can click any point (or search an address) to see that
location's past precipitation. It also collects surface weather observations
(temperature, pressure, humidity, …) to serve as features for a future
precipitation-prediction model.

## Architecture

| Service     | What it does                                                                 |
|-------------|------------------------------------------------------------------------------|
| `db`        | TimescaleDB (Postgres). Schema/hypertables created from `db/init.sql`.        |
| `ingestor`  | Every `INGEST_INTERVAL_MINUTES`: downloads radar GIF + ARSO weather XML, decodes, archives full-res frames, writes precipitation grid, named-location readings, and weather observations. |
| `api`       | FastAPI + Uvicorn. REST API, Swagger at `/docs`, serves the map GUI at `/`.   |

Data stored:
- **`precip_grid`** — coarse-grid precipitation per timestamp (powers click-anywhere queries).
- **`location_readings`** — precipitation/storm flag for registered named locations.
- **`radar_frames`** — archived full-resolution frames (GIF + NumPy array) on a volume = ML training corpus.
- **`weather_obs`** — per-station temperature, pressure, humidity, dew point, wind.

## Quick start

```bash
cp .env.example .env        # adjust credentials/intervals if you like
docker compose up --build
```

Then open:
- **Map GUI:** http://localhost:8000/
- **Swagger / OpenAPI docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

The ingestor runs one cycle immediately on startup, then every
`INGEST_INTERVAL_MINUTES` (default 10). Precipitation history accumulates over time —
right after first launch the graphs will be sparse until several cycles have run.

## API overview

| Method & path                         | Description                                            |
|---------------------------------------|--------------------------------------------------------|
| `GET /health`                         | Liveness + last ingest timestamp + frame count         |
| `GET /locations`                      | List registered locations                              |
| `POST /locations`                     | Add a location by address (geocoded) + alert radius    |
| `GET /locations/{name}`               | Location details                                       |
| `GET /locations/{name}/history`       | Precipitation series for a named location              |
| `GET /precip/history?lat&lon`         | **Click-anywhere** precipitation series for a point    |
| `GET /precip/by-address?address=`     | Precipitation series for a geocoded address            |
| `GET /radar/latest`                   | Most recent raw radar GIF                              |
| `GET /radar/meta`                     | Map bounds + timestamp for the radar overlay           |
| `GET /radar/overlay.png?time=`        | Transparent precipitation overlay (latest, or nearest `time`) |
| `GET /weather/history?lat&lon`        | Weather series from the nearest station                |

All history endpoints accept optional `from` and `to` ISO-8601 query params
(default: last 24 h).

Example:
```bash
curl "http://localhost:8000/precip/history?lat=46.05&lon=14.51"
curl -X POST http://localhost:8000/locations \
  -H "Content-Type: application/json" \
  -d '{"name":"home","address":"Ljubljana, Slovenia","radius_km":5}'
```

## Configuration

All settings come from environment variables (see `.env.example`):

| Variable                  | Default | Meaning                                        |
|---------------------------|---------|------------------------------------------------|
| `INGEST_INTERVAL_MINUTES` | `10`    | Minutes between radar/weather polls            |
| `GRID_CELL_PIXELS`        | `4`     | Downsample factor; bigger = coarser grid, less storage |
| `RADAR_IMAGE_URL`         | ARSO    | Source radar GIF                               |
| `WEATHER_XML_URL`         | ARSO    | Source observations XML                        |
| `FRAMES_DIR`              | `/data/frames` | Where full-res frames are archived       |

## Future: precipitation prediction (ML)

This release lays the groundwork for an "ML predictive radar" without training a model yet:
- **`radar_frames`** archives every distinct full-resolution frame (deduped by hash) as a
  NumPy array — a sequence suitable for training a spatiotemporal model.
- **`weather_obs`** collects temperature / pressure / humidity / wind per station.
- **Season** is derivable from each row's `time`, so no extra collection is needed.

Once enough data has accumulated, a model can be trained on the frame sequence + weather
features to forecast precipitation a few hours ahead.

## Notes

- The original MySQL CLI (`radar_main.py`, `radar_analyzer.py`, `db_handler.py`) has been
  superseded by the `app/` package and removed; its radar-decode, coordinate-transform,
  and geocoding logic was ported and hardened (retries, bounds-safe sampling, fixed
  geocoding None-handling). The old files remain in git history.
- Storage: Slovenia's radar image is small; archived frames and TimescaleDB compression
  keep long-term storage to a few GB/year.
