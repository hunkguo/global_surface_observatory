"""OpenStreetMap Nominatim 地理编码客户端。

使用条款：https://operations.osmfoundation.org/policies/nominatim/
- 必须标识 User-Agent
- 速率 ≤1 req/s
- 进程内 cache，避免重复查询
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GSO/0.1 (+https://github.com/hunkguo/global_surface_observatory)"
_MIN_INTERVAL_S = 1.0


@dataclass(frozen=True)
class GeoLocation:
    query: str
    lat: float
    lon: float
    display_name: str


_cache: dict[str, GeoLocation | None] = {}
_lock = threading.Lock()
_last_call_ts: float = 0.0


def _rate_limit() -> None:
    global _last_call_ts
    with _lock:
        now = time.time()
        wait = _MIN_INTERVAL_S - (now - _last_call_ts)
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.time()


def geocode(city: str, timeout: float = 15.0) -> GeoLocation | None:
    """城市名 -> GeoLocation；查不到返回 None。支持中英文等任意语言。"""
    key = city.strip().lower()
    if not key:
        return None
    if key in _cache:
        return _cache[key]

    _rate_limit()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": city, "format": "json", "limit": 1, "accept-language": "en"},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json() or []
    except Exception:
        _cache[key] = None
        return None

    if not data:
        _cache[key] = None
        return None
    hit = data[0]
    loc = GeoLocation(
        query=city,
        lat=float(hit["lat"]),
        lon=float(hit["lon"]),
        display_name=hit.get("display_name") or city,
    )
    _cache[key] = loc
    return loc
