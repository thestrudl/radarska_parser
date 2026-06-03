"""Radar image handling: download, decode, coordinate transforms, sampling.

Ports and hardens the logic from the original ``radar_analyzer.py``:
 - retry/timeout on download
 - GIF -> numpy palette-index grid (vectorized color->mm/h lookup)
 - lat/lon <-> image x/y transform
 - bounds-safe point/area sampling
 - downsampling to a coarse grid for fast click-anywhere queries
"""
from __future__ import annotations

import hashlib
import io
import logging
import time
from dataclasses import dataclass

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)

# Palette index -> precipitation in mm/h (from original COLOR_SCALE).
COLOR_SCALE: dict[int, float] = {
    19: 0.25, 18: 0.5, 17: 0.75, 16: 1, 15: 1.5, 14: 2, 13: 3.5, 12: 5,
    11: 8, 10: 15, 9: 30, 8: 50, 7: 75, 5: 100, 4: 125,
}

# Linear transform constants from the original code (lon/lat -> pixel x/y).
_LON_A, _LON_B = 152.302, -1838.83
_LAT_A, _LAT_B = -224.91, 10710.4
_RADIUS_PX_PER_KM = 2.012


@dataclass
class RadarFrame:
    """A decoded radar frame."""

    indices: np.ndarray  # 2-D uint8 array of palette indices (shape: y, x)
    mm_h: np.ndarray  # 2-D float array of precipitation in mm/h
    palette_hash: str  # hash of raw indices, used to dedupe unchanged frames
    raw_gif: bytes

    @property
    def height(self) -> int:
        return self.indices.shape[0]

    @property
    def width(self) -> int:
        return self.indices.shape[1]


def _build_lookup() -> np.ndarray:
    """Vectorized palette-index -> mm/h lookup table (index 0..255)."""
    lut = np.zeros(256, dtype=np.float32)
    for idx, val in COLOR_SCALE.items():
        lut[idx] = val
    return lut


_LUT = _build_lookup()


def download_radar(url: str, retries: int = 3, timeout: int = 20) -> bytes:
    """Download the radar GIF with retries. Returns raw bytes."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as err:
            last_err = err
            logger.warning("Radar download attempt %d/%d failed: %s", attempt, retries, err)
            time.sleep(min(2 ** attempt, 10))
    raise RuntimeError(f"Failed to download radar image after {retries} attempts") from last_err


def decode_frame(raw_gif: bytes) -> RadarFrame:
    """Decode raw GIF bytes into a RadarFrame (palette indices + mm/h)."""
    image = Image.open(io.BytesIO(raw_gif))
    indices = np.asarray(image.convert("P"), dtype=np.uint8)
    mm_h = _LUT[indices]
    palette_hash = hashlib.sha256(indices.tobytes()).hexdigest()
    return RadarFrame(indices=indices, mm_h=mm_h, palette_hash=palette_hash, raw_gif=raw_gif)


def lonlat_to_xy(lat: float, lon: float) -> tuple[float, float]:
    """Convert lat/lon to (x, y) pixel coordinates in the radar image."""
    x = lon * _LON_A + _LON_B
    y = lat * _LAT_A + _LAT_B
    return x, y


def xy_to_lonlat(x: float, y: float) -> tuple[float, float]:
    """Inverse of ``lonlat_to_xy``: image pixel (x, y) -> (lat, lon)."""
    lon = (x - _LON_B) / _LON_A
    lat = (y - _LAT_B) / _LAT_A
    return lat, lon


def geo_bounds(width: int, height: int) -> list[list[float]]:
    """Leaflet [[south, west], [north, east]] bounds for an image of this size.

    Pixel (0, 0) is the NW corner; (width, height) is the SE corner.
    """
    lat_n, lon_w = xy_to_lonlat(0, 0)
    lat_s, lon_e = xy_to_lonlat(width, height)
    return [[lat_s, lon_w], [lat_n, lon_e]]


def km_to_radius_px(radius_km: float) -> float:
    return radius_km * _RADIUS_PX_PER_KM


def overlay_png(gif_path: str, alpha: int = 200) -> bytes:
    """Render a frame as a transparent PNG: only precipitation pixels are opaque.

    Keeps the GIF's own palette colors for precipitation and makes every other
    pixel (basemap, borders, background) fully transparent so it overlays cleanly
    on top of a web map.
    """
    img = Image.open(io.BytesIO(_read_bytes(gif_path)))
    idx = np.asarray(img.convert("P"), dtype=np.uint8)
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    precip_mask = np.isin(idx, np.array(list(COLOR_SCALE.keys()), dtype=np.uint8))
    alpha_channel = np.where(precip_mask, alpha, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha_channel])
    out = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(out, format="PNG")
    return out.getvalue()


def image_size(gif_path: str) -> tuple[int, int]:
    """Return (width, height) of a stored GIF without decoding pixel data."""
    with Image.open(gif_path) as img:
        return img.size


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def sample_point(frame: RadarFrame, x: float, y: float) -> float:
    """mm/h at a single pixel, bounds-clamped."""
    xi = int(round(x))
    yi = int(round(y))
    if not (0 <= xi < frame.width and 0 <= yi < frame.height):
        return 0.0
    return float(frame.mm_h[yi, xi])


def sample_area(frame: RadarFrame, x: float, y: float, radius_px: float) -> tuple[bool, float]:
    """Return (storm_flag, mm/h at center) for a square window around (x, y).

    Bounds-safe (the original ``read_pixel`` could index out of range near edges).
    Storm flag mirrors original logic: a palette index in [4, 10] within the window.
    """
    xi = int(round(x))
    yi = int(round(y))
    r = max(0, int(np.ceil(radius_px)))

    x0, x1 = max(0, xi - r), min(frame.width, xi + r + 1)
    y0, y1 = max(0, yi - r), min(frame.height, yi + r + 1)

    storm = False
    if x1 > x0 and y1 > y0:
        window = frame.indices[y0:y1, x0:x1]
        storm = bool(np.any((window >= 4) & (window <= 10)))

    return storm, sample_point(frame, x, y)


def downsample_grid(frame: RadarFrame, cell_pixels: int) -> np.ndarray:
    """Downsample mm/h to a coarse grid by taking the max over each cell block.

    Max (not mean) preserves storm peaks. Returns a 2-D array (cell_y, cell_x).
    """
    cell_pixels = max(1, cell_pixels)
    h, w = frame.mm_h.shape
    ny = h // cell_pixels
    nx = w // cell_pixels
    if ny == 0 or nx == 0:
        return frame.mm_h.copy()
    trimmed = frame.mm_h[: ny * cell_pixels, : nx * cell_pixels]
    blocks = trimmed.reshape(ny, cell_pixels, nx, cell_pixels)
    return blocks.max(axis=(1, 3))


def xy_to_cell(x: float, y: float, cell_pixels: int) -> tuple[int, int]:
    """Map image pixel (x, y) to coarse-grid cell indices (cell_x, cell_y)."""
    cell_pixels = max(1, cell_pixels)
    return int(x // cell_pixels), int(y // cell_pixels)
