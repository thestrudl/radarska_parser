"""Fetch and parse ARSO surface-observation XML into weather records.

Provides the temperature / pressure / humidity variables that will feed the
future precipitation-prediction model. Each <metData> element is one station
observation. Verified field tags: <t>, <msl>/<p>, <rh>, <td>, <ff_val>, <dd_val>.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
from lxml import etree

logger = logging.getLogger(__name__)


@dataclass
class WeatherObs:
    station: str
    lat: float | None
    lon: float | None
    temp: float | None
    pressure_msl: float | None
    humidity: float | None
    dew_point: float | None
    wind_speed: float | None
    wind_dir: float | None


def _text(node, tag: str) -> str | None:
    el = node.find(tag)
    if el is not None and el.text is not None and el.text.strip() != "":
        return el.text.strip()
    return None


def _float(node, tag: str) -> float | None:
    raw = _text(node, tag)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def download_weather_xml(url: str, retries: int = 3, timeout: int = 20) -> bytes:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as err:
            last_err = err
            logger.warning("Weather download attempt %d/%d failed: %s", attempt, retries, err)
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Failed to download weather XML after {retries} attempts") from last_err


def parse_weather(raw_xml: bytes) -> list[WeatherObs]:
    """Parse ARSO observation XML into a list of WeatherObs."""
    root = etree.fromstring(raw_xml)
    out: list[WeatherObs] = []
    for node in root.iter("metData"):
        station = _text(node, "domain_longTitle") or _text(node, "domain_title") or "unknown"
        out.append(
            WeatherObs(
                station=station,
                lat=_float(node, "domain_lat"),
                lon=_float(node, "domain_lon"),
                temp=_float(node, "t"),
                # Prefer mean-sea-level pressure; fall back to station pressure.
                pressure_msl=_float(node, "msl") or _float(node, "p"),
                humidity=_float(node, "rh"),
                dew_point=_float(node, "td"),
                wind_speed=_float(node, "ff_val"),
                wind_dir=_float(node, "dd_val"),
            )
        )
    return out
