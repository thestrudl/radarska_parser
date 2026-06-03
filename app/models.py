"""SQLAlchemy ORM models mirroring the TimescaleDB schema in db/init.sql.

Note: the hypertables (location_readings, precip_grid, weather_obs) use a
composite primary key that includes the partitioning column ``time``, which is
a TimescaleDB requirement.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    radius: Mapped[float] = mapped_column(Float)
    radiuspx: Mapped[float] = mapped_column(Float)


class LocationReading(Base):
    __tablename__ = "location_readings"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mm_h: Mapped[float] = mapped_column(Float)
    storm: Mapped[bool] = mapped_column(Boolean, default=False)


class PrecipGrid(Base):
    __tablename__ = "precip_grid"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    cell_x: Mapped[int] = mapped_column(Integer, primary_key=True)
    cell_y: Mapped[int] = mapped_column(Integer, primary_key=True)
    mm_h: Mapped[float] = mapped_column(Float)


class RadarFrameRow(Base):
    __tablename__ = "radar_frames"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    gif_path: Mapped[str] = mapped_column(Text)
    npy_path: Mapped[str] = mapped_column(Text)
    palette_hash: Mapped[str] = mapped_column(String(64), index=True)


class WeatherObsRow(Base):
    __tablename__ = "weather_obs"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    station: Mapped[str] = mapped_column(String(128), primary_key=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    temp: Mapped[float | None] = mapped_column(Float)
    pressure_msl: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    dew_point: Mapped[float | None] = mapped_column(Float)
    wind_speed: Mapped[float | None] = mapped_column(Float)
    wind_dir: Mapped[float | None] = mapped_column(Float)
