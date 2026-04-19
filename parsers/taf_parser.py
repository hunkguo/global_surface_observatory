"""TAF 解析：把各数据源的 JSON 规约为统一 schema。"""
from __future__ import annotations

from typing import Any

from parsers.metar_parser import _iso  # noqa: F401  时间解析复用


def from_awc(item: dict) -> dict:
    return {
        "icao": (item.get("icaoId") or "").upper() or None,
        "issue_time": _iso(item.get("issueTime")),
        "valid_from": _iso(item.get("validTimeFrom")),
        "valid_to": _iso(item.get("validTimeTo")),
        "raw_text": item.get("rawTAF") or item.get("rawOb"),
    }


def from_avwx(data: dict) -> dict:
    time_obj = data.get("time") or {}
    start = data.get("start_time") or {}
    end = data.get("end_time") or {}
    station = data.get("station") or (data.get("meta") or {}).get("station")
    return {
        "icao": (station or "").upper() or None,
        "issue_time": _iso(time_obj.get("dt")),
        "valid_from": _iso(start.get("dt")),
        "valid_to": _iso(end.get("dt")),
        "raw_text": data.get("raw"),
    }
