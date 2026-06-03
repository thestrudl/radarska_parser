"""FastAPI application: REST API + auto Swagger (/docs) + static map GUI."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import radar
from app.config import get_settings
from app.db import get_session
from app.geocode import geocode
from app.models import (
    Location,
    LocationReading,
    PrecipGrid,
    RadarFrameRow,
    WeatherObsRow,
)
from app.schemas import (
    HealthResponse,
    LocationCreate,
    LocationHistory,
    LocationOut,
    PrecipHistory,
    RadarMeta,
    TimePoint,
    WeatherHistory,
    WeatherPoint,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Slovenian Radar Precipitation API",
    description=(
        "Query historic precipitation from the ARSO Slovenia weather radar for any "
        "map point or address, manage named locations, and access collected weather "
        "observations. Interactive docs at /docs."
    ),
    version="1.0.0",
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

DEFAULT_WINDOW = timedelta(hours=24)


def _resolve_window(frm: datetime | None, to: datetime | None) -> tuple[datetime, datetime]:
    to = to or datetime.now(timezone.utc)
    frm = frm or (to - DEFAULT_WINDOW)
    return frm, to


def _frame_row(db: Session, when: datetime | None = None) -> RadarFrameRow | None:
    """Most recent frame, or the frame closest in time to ``when``."""
    if when is None:
        return db.execute(
            select(RadarFrameRow).order_by(RadarFrameRow.time.desc()).limit(1)
        ).scalar_one_or_none()
    diff = func.abs(func.extract("epoch", RadarFrameRow.time - when))
    return db.execute(
        select(RadarFrameRow).order_by(diff).limit(1)
    ).scalar_one_or_none()


# --- Health -------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(db: Session = Depends(get_session)) -> HealthResponse:
    last = db.execute(select(func.max(RadarFrameRow.time))).scalar_one_or_none()
    count = db.execute(select(func.count()).select_from(RadarFrameRow)).scalar_one()
    return HealthResponse(status="ok", last_ingest=last, frames_stored=count)


# --- Locations ----------------------------------------------------------------
@app.get("/locations", response_model=list[LocationOut], tags=["locations"])
def list_locations(db: Session = Depends(get_session)) -> list[Location]:
    return list(db.execute(select(Location).order_by(Location.name)).scalars())


@app.post("/locations", response_model=LocationOut, status_code=201, tags=["locations"])
def create_location(payload: LocationCreate, db: Session = Depends(get_session)) -> Location:
    coords = geocode(payload.address)
    if coords is None:
        raise HTTPException(status_code=422, detail=f"Could not geocode address: {payload.address}")
    lat, lon = coords
    x, y = radar.lonlat_to_xy(lat, lon)
    radiuspx = radar.km_to_radius_px(payload.radius_km)

    existing = db.execute(select(Location).where(Location.name == payload.name)).scalar_one_or_none()
    if existing:
        existing.address = payload.address
        existing.lat, existing.lon = lat, lon
        existing.x, existing.y = x, y
        existing.radius, existing.radiuspx = payload.radius_km, radiuspx
        loc = existing
    else:
        loc = Location(
            name=payload.name, address=payload.address, lat=lat, lon=lon,
            x=x, y=y, radius=payload.radius_km, radiuspx=radiuspx,
        )
        db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@app.get("/locations/{name}", response_model=LocationOut, tags=["locations"])
def get_location(name: str, db: Session = Depends(get_session)) -> Location:
    loc = db.execute(select(Location).where(Location.name == name)).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail=f"No location named {name!r}")
    return loc


@app.get("/locations/{name}/history", response_model=LocationHistory, tags=["locations"])
def location_history(
    name: str,
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_session),
) -> LocationHistory:
    loc = db.execute(select(Location).where(Location.name == name)).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail=f"No location named {name!r}")
    frm, to = _resolve_window(frm, to)
    rows = db.execute(
        select(LocationReading.time, LocationReading.mm_h)
        .where(LocationReading.location_id == loc.id)
        .where(LocationReading.time >= frm, LocationReading.time <= to)
        .order_by(LocationReading.time)
    ).all()
    return LocationHistory(name=name, points=[TimePoint(time=t, mm_h=v) for t, v in rows])


# --- Click-anywhere precipitation ---------------------------------------------
def _precip_history_for_point(db: Session, lat: float, lon: float,
                              frm: datetime | None, to: datetime | None) -> PrecipHistory:
    x, y = radar.lonlat_to_xy(lat, lon)
    cell_x, cell_y = radar.xy_to_cell(x, y, settings.grid_cell_pixels)
    frm, to = _resolve_window(frm, to)
    rows = db.execute(
        select(PrecipGrid.time, PrecipGrid.mm_h)
        .where(PrecipGrid.cell_x == cell_x, PrecipGrid.cell_y == cell_y)
        .where(PrecipGrid.time >= frm, PrecipGrid.time <= to)
        .order_by(PrecipGrid.time)
    ).all()
    return PrecipHistory(
        lat=lat, lon=lon, cell_x=cell_x, cell_y=cell_y,
        points=[TimePoint(time=t, mm_h=v) for t, v in rows],
    )


@app.get("/precip/history", response_model=PrecipHistory, tags=["precipitation"])
def precip_history(
    lat: float = Query(..., ge=45.0, le=47.5),
    lon: float = Query(..., ge=13.0, le=17.0),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_session),
) -> PrecipHistory:
    """Precipitation time series at any map point (maps lat/lon -> radar grid cell)."""
    return _precip_history_for_point(db, lat, lon, frm, to)


@app.get("/precip/by-address", response_model=PrecipHistory, tags=["precipitation"])
def precip_by_address(
    address: str,
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_session),
) -> PrecipHistory:
    """Precipitation time series for a geocoded address ('graph for my address')."""
    coords = geocode(address)
    if coords is None:
        raise HTTPException(status_code=422, detail=f"Could not geocode address: {address}")
    return _precip_history_for_point(db, coords[0], coords[1], frm, to)


# --- Radar image --------------------------------------------------------------
@app.get("/radar/latest", tags=["radar"])
def radar_latest(db: Session = Depends(get_session)):
    """Return the most recently archived radar GIF (raw, with ARSO basemap)."""
    row = _frame_row(db)
    if row is None or not os.path.exists(row.gif_path):
        raise HTTPException(status_code=404, detail="No radar frame available yet")
    return FileResponse(row.gif_path, media_type="image/gif",
                        headers={"X-Frame-Time": row.time.isoformat()})


@app.get("/radar/meta", response_model=RadarMeta, tags=["radar"])
def radar_meta(db: Session = Depends(get_session)) -> RadarMeta:
    """Geographic bounds + latest timestamp for placing the radar overlay on a map."""
    row = _frame_row(db)
    if row is None or not os.path.exists(row.gif_path):
        raise HTTPException(status_code=404, detail="No radar frame available yet")
    width, height = radar.image_size(row.gif_path)
    return RadarMeta(
        time=row.time,
        bounds=radar.geo_bounds(width, height),
        width=width,
        height=height,
    )


@app.get("/radar/overlay.png", tags=["radar"])
def radar_overlay(
    time: datetime | None = None,
    db: Session = Depends(get_session),
):
    """Transparent PNG overlay (precipitation only) for the latest frame, or the
    frame nearest ``time`` when given. Designed for Leaflet's imageOverlay."""
    row = _frame_row(db, time)
    if row is None or not os.path.exists(row.gif_path):
        raise HTTPException(status_code=404, detail="No radar frame available yet")
    png = radar.overlay_png(row.gif_path)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "X-Frame-Time": row.time.isoformat(),
            "Cache-Control": "public, max-age=86400",
        },
    )


# --- Weather ------------------------------------------------------------------
@app.get("/weather/history", response_model=WeatherHistory, tags=["weather"])
def weather_history(
    lat: float = Query(..., ge=45.0, le=47.5),
    lon: float = Query(..., ge=13.0, le=17.0),
    frm: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_session),
) -> WeatherHistory:
    """Weather observations from the station nearest to the given point."""
    frm, to = _resolve_window(frm, to)
    # Nearest station by squared planar distance (fine at this scale).
    dist = (WeatherObsRow.lat - lat) * (WeatherObsRow.lat - lat) + (
        WeatherObsRow.lon - lon
    ) * (WeatherObsRow.lon - lon)
    nearest = db.execute(
        select(WeatherObsRow.station, WeatherObsRow.lat, WeatherObsRow.lon)
        .where(WeatherObsRow.lat.isnot(None), WeatherObsRow.lon.isnot(None))
        .order_by(dist)
        .limit(1)
    ).first()
    if nearest is None:
        raise HTTPException(status_code=404, detail="No weather observations available yet")
    station, slat, slon = nearest
    rows = db.execute(
        select(WeatherObsRow)
        .where(WeatherObsRow.station == station)
        .where(WeatherObsRow.time >= frm, WeatherObsRow.time <= to)
        .order_by(WeatherObsRow.time)
    ).scalars().all()
    return WeatherHistory(
        station=station, lat=slat, lon=slon,
        points=[
            WeatherPoint(
                time=r.time, temp=r.temp, pressure_msl=r.pressure_msl,
                humidity=r.humidity, dew_point=r.dew_point,
                wind_speed=r.wind_speed, wind_dir=r.wind_dir,
            )
            for r in rows
        ],
    )


# --- Frontend -----------------------------------------------------------------
@app.get("/", include_in_schema=False)
def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return RedirectResponse(url="/docs")


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
