"""Scheduled ingestion worker.

Every INGEST_INTERVAL_MINUTES it:
 1. downloads the radar GIF, decodes it, archives the frame (gif + npy) and
    records grid + named-location precipitation,
 2. downloads the ARSO weather XML and stores per-station observations.

Each step is wrapped so a single failure is logged and the loop survives
(the original ``run_periodic_check`` would crash the whole process on any error).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import numpy as np
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import radar, weather
from app.config import get_settings
from app.db import SessionLocal, wait_for_db
from app.models import Location, LocationReading, PrecipGrid, RadarFrameRow, WeatherObsRow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ingestor")

settings = get_settings()


def _archive_frame(frame: radar.RadarFrame, ts: datetime) -> tuple[str, str]:
    os.makedirs(settings.frames_dir, exist_ok=True)
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    gif_path = os.path.join(settings.frames_dir, f"{stamp}.gif")
    npy_path = os.path.join(settings.frames_dir, f"{stamp}.npy")
    with open(gif_path, "wb") as fh:
        fh.write(frame.raw_gif)
    np.save(npy_path, frame.indices)
    return gif_path, npy_path


def ingest_radar() -> None:
    ts = datetime.now(timezone.utc)
    raw = radar.download_radar(settings.radar_image_url)
    frame = radar.decode_frame(raw)

    with SessionLocal() as session:
        # Dedupe: skip storing a frame identical to the most recent one.
        last_hash = session.execute(
            select(RadarFrameRow.palette_hash).order_by(RadarFrameRow.time.desc()).limit(1)
        ).scalar_one_or_none()
        if last_hash == frame.palette_hash:
            logger.info("Radar frame unchanged (hash %s); skipping archive.", frame.palette_hash[:8])
        else:
            gif_path, npy_path = _archive_frame(frame, ts)
            session.add(RadarFrameRow(time=ts, gif_path=gif_path, npy_path=npy_path,
                                      palette_hash=frame.palette_hash))

        # Coarse grid -> precip_grid (only cells with precipitation, to save space).
        grid = radar.downsample_grid(frame, settings.grid_cell_pixels)
        ys, xs = np.nonzero(grid > 0)
        if len(xs):
            rows = [
                {"time": ts, "cell_x": int(cx), "cell_y": int(cy), "mm_h": float(grid[cy, cx])}
                for cy, cx in zip(ys, xs)
            ]
            session.execute(
                pg_insert(PrecipGrid).values(rows).on_conflict_do_nothing(
                    index_elements=["time", "cell_x", "cell_y"]
                )
            )
        logger.info("Stored %d non-zero grid cells.", len(xs))

        # Named locations.
        for loc in session.execute(select(Location)).scalars():
            storm, mm_h = radar.sample_area(frame, loc.x, loc.y, loc.radiuspx)
            session.execute(
                pg_insert(LocationReading)
                .values(time=ts, location_id=loc.id, mm_h=mm_h, storm=storm)
                .on_conflict_do_nothing(index_elements=["time", "location_id"])
            )
            if storm:
                logger.info("Storm detected at location %s", loc.name)

        session.commit()


def ingest_weather() -> None:
    ts = datetime.now(timezone.utc)
    raw = weather.download_weather_xml(settings.weather_xml_url)
    observations = weather.parse_weather(raw)
    if not observations:
        logger.warning("No weather observations parsed.")
        return
    with SessionLocal() as session:
        for obs in observations:
            session.execute(
                pg_insert(WeatherObsRow)
                .values(
                    time=ts, station=obs.station, lat=obs.lat, lon=obs.lon,
                    temp=obs.temp, pressure_msl=obs.pressure_msl, humidity=obs.humidity,
                    dew_point=obs.dew_point, wind_speed=obs.wind_speed, wind_dir=obs.wind_dir,
                )
                .on_conflict_do_nothing(index_elements=["time", "station"])
            )
        session.commit()
    logger.info("Stored %d weather observations.", len(observations))


def run_cycle() -> None:
    """One ingestion cycle. Each source isolated so one failure won't skip the other."""
    for name, fn in (("radar", ingest_radar), ("weather", ingest_weather)):
        try:
            fn()
        except Exception:  # noqa: BLE001 - keep the scheduler alive
            logger.exception("Ingestion step %r failed", name)


def main() -> None:
    wait_for_db()
    logger.info("Running initial ingestion cycle...")
    run_cycle()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_cycle,
        "interval",
        minutes=settings.ingest_interval_minutes,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Scheduler started (every %d min).", settings.ingest_interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Ingestor shutting down.")


if __name__ == "__main__":
    main()
