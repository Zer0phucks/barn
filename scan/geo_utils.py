"""Shared coordinate helpers for the scanner scripts and webui.

The single canonical copy of web_mercator_to_latlng(), replacing the three
independent copies that lived in db.py, condition_scanner.py, and
backfill_streetview.py.

Parcel CSV exports carry centroids in EPSG:3857 (Web Mercator) under a few
different column names depending on which export produced them, so
extract_centroid() probes all the spellings we've seen.
"""
from __future__ import annotations

import json
import math

__all__ = [
    "web_mercator_to_latlng",
    "extract_centroid",
    "derive_latlng",
]


def web_mercator_to_latlng(x: float, y: float) -> tuple[float, float]:
    """Convert EPSG:3857 (Web Mercator) coordinates to WGS84 (lat, lng)."""
    lng = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return lat, lng


def _coerce_row_json(row_json: str | dict | None) -> dict | None:
    """Accept a parcel row_json as either a JSON string or an already-parsed dict."""
    if not row_json:
        return None
    if isinstance(row_json, str):
        try:
            row_json = json.loads(row_json)
        except json.JSONDecodeError:
            return None
    return row_json if isinstance(row_json, dict) else None


def extract_centroid(row_json: str | dict | None) -> tuple[float, float] | None:
    """Extract (x, y) Web Mercator coordinates from a parcel's row_json blob.

    Handles the different key names seen across CSV export formats. Returns
    None when either ordinate is missing or zero — 0,0 is Null Island, never a
    real Bay Area parcel, and is what the exports emit for "unknown".
    """
    parcel = _coerce_row_json(row_json)
    if parcel is None:
        return None
    try:
        x = float(parcel.get("CENTROID_X") or parcel.get("X_CORD") or parcel.get("x") or 0)
        y = float(parcel.get("CENTROID_Y") or parcel.get("Y_CORD") or parcel.get("y") or 0)
    except (TypeError, ValueError):
        return None
    if not x or not y:
        return None
    return x, y


def derive_latlng(row_json: str | dict | None) -> tuple[float, float] | None:
    """Convenience: parcel row_json -> (lat, lng), or None if unavailable."""
    centroid = extract_centroid(row_json)
    if centroid is None:
        return None
    return web_mercator_to_latlng(*centroid)
