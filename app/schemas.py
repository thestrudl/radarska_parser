"""Pydantic request/response schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    last_ingest: datetime | None = None
    frames_stored: int = 0


class LocationCreate(BaseModel):
    name: str = Field(..., examples=["home"])
    address: str = Field(..., examples=["Ljubljana, Slovenia"])
    radius_km: float = Field(5.0, gt=0, examples=[5.0])


class LocationOut(BaseModel):
    name: str
    address: str | None
    lat: float
    lon: float
    radius: float

    model_config = {"from_attributes": True}


class TimePoint(BaseModel):
    time: datetime
    mm_h: float


class PrecipHistory(BaseModel):
    lat: float
    lon: float
    cell_x: int
    cell_y: int
    points: list[TimePoint]


class LocationHistory(BaseModel):
    name: str
    points: list[TimePoint]


class RadarMeta(BaseModel):
    time: datetime
    # Leaflet bounds: [[south, west], [north, east]]
    bounds: list[list[float]]
    width: int
    height: int


class WeatherPoint(BaseModel):
    time: datetime
    temp: float | None = None
    pressure_msl: float | None = None
    humidity: float | None = None
    dew_point: float | None = None
    wind_speed: float | None = None
    wind_dir: float | None = None


class WeatherHistory(BaseModel):
    station: str
    lat: float | None
    lon: float | None
    points: list[WeatherPoint]
