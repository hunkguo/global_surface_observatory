"""METAR 解析：把各数据源的 JSON 规约为统一 schema。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _iso(value: Any) -> str | None:
    """接受 AWC 的 epoch 秒 / 'YYYY-MM-DD HH:MM:SS' / AVWX 的 ISO 字符串。"""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    value = str(value).strip()
    if not value:
        return None
    if value.endswith("Z") or "+" in value[10:]:
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return value


def from_awc(item: dict) -> dict:
    """AWC /api/data/metar?format=json 单条记录 -> 统一 schema."""
    return {
        "icao": (item.get("icaoId") or "").upper() or None,
        "observation_time": _iso(item.get("reportTime") or item.get("obsTime")),
        "raw_text": item.get("rawOb"),
        "sanitized_text": None,
        "temperature_c": _num(item.get("temp")),
        "dewpoint_c": _num(item.get("dewp")),
        "wind_dir": _int(item.get("wdir")),
        "wind_speed": _num(item.get("wspd")),
        "gust": _num(item.get("wgst")),
        "visibility": str(item["visib"]) if item.get("visib") is not None else None,
        "altimeter": _num(item.get("altim")),
        "flight_category": item.get("fltCat") or item.get("fltcat"),
    }


def from_avwx(data: dict) -> dict:
    """AVWX /api/metar/<ICAO> 响应 -> 统一 schema."""
    station = data.get("station") or (data.get("meta") or {}).get("station")
    wind_dir = data.get("wind_direction") or {}
    wind_speed = data.get("wind_speed") or {}
    wind_gust = data.get("wind_gust") or {}
    temp = data.get("temperature") or {}
    dew = data.get("dewpoint") or {}
    visibility = data.get("visibility") or {}
    altim = data.get("altimeter") or {}
    return {
        "icao": (station or "").upper() or None,
        "observation_time": _iso((data.get("time") or {}).get("dt")),
        "raw_text": data.get("raw"),
        "sanitized_text": data.get("sanitized"),
        "temperature_c": _num(temp.get("value")),
        "dewpoint_c": _num(dew.get("value")),
        "wind_dir": _int(wind_dir.get("value")),
        "wind_speed": _num(wind_speed.get("value")),
        "gust": _num(wind_gust.get("value")),
        "visibility": str(visibility.get("repr")) if visibility.get("repr") is not None else None,
        "altimeter": _num(altim.get("value")),
        "flight_category": data.get("flight_rules"),
    }
