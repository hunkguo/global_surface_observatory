"""AWC cache 下载 + 解析：metars.cache.csv.gz / tafs.cache.xml.gz。

客户端保持无状态：下载 + 解析；调用方负责读/写 http_cache_state 和 DB。
"""
from __future__ import annotations

import csv
import gzip
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests

METAR_CACHE_URL = "https://aviationweather.gov/data/cache/metars.cache.csv.gz"
TAF_CACHE_URL = "https://aviationweather.gov/data/cache/tafs.cache.xml.gz"
SOURCE_CODE = "awc"
USER_AGENT = "GSO/0.1 (+https://github.com/hunkguo/global_surface_observatory)"

INHG_TO_HPA = 33.86389


@dataclass
class FetchResult:
    status: int          # 200 / 304 / 其他
    etag: str | None
    last_modified: str | None
    body: bytes | None   # 200 时为解压前的响应 body (.gz)，304/其他为 None
    elapsed_s: float


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


def download_if_changed(
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    timeout: float = 60.0,
    user_agent: str = USER_AGENT,
) -> FetchResult:
    import time as _time

    headers = {"User-Agent": user_agent}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    t0 = _time.time()
    resp = requests.get(url, headers=headers, timeout=timeout)
    elapsed = _time.time() - t0
    new_etag = resp.headers.get("ETag")
    new_last_mod = resp.headers.get("Last-Modified")

    if resp.status_code == 304:
        return FetchResult(304, new_etag or etag, new_last_mod or last_modified, None, elapsed)
    resp.raise_for_status()
    return FetchResult(resp.status_code, new_etag, new_last_mod, resp.content, elapsed)


def _decompress(body: bytes) -> bytes:
    return gzip.decompress(body)


def parse_metars_csv(body: bytes) -> list[dict]:
    """解析 metars.cache.csv.gz 的原文 bytes，返回统一 schema 字典列表。

    注意：
    - altim_in_hg 单位是 inHg，统一转为 hPa (mb) 入库，和 API 模式保持一致
    - metar_type 字段值可能为 METAR / SPECI
    """
    text = _decompress(body).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    out: list[dict] = []
    for row in reader:
        icao = (row.get("station_id") or "").strip().upper()
        raw = (row.get("raw_text") or "").strip()
        obs = (row.get("observation_time") or "").strip() or None
        if not icao or not raw:
            continue
        altim_inhg = _to_float(row.get("altim_in_hg"))
        altimeter_hpa = round(altim_inhg * INHG_TO_HPA, 2) if altim_inhg is not None else None
        out.append({
            "icao": icao,
            "source_code": SOURCE_CODE,
            "observation_time": obs,
            "raw_text": raw,
            "sanitized_text": None,
            "temperature_c": _to_float(row.get("temp_c")),
            "dewpoint_c": _to_float(row.get("dewpoint_c")),
            "wind_dir": _to_int(row.get("wind_dir_degrees")),
            "wind_speed": _to_float(row.get("wind_speed_kt")),
            "gust": _to_float(row.get("wind_gust_kt")),
            "visibility": (row.get("visibility_statute_mi") or "").strip() or None,
            "altimeter": altimeter_hpa,
            "sea_level_pressure_mb": _to_float(row.get("sea_level_pressure_mb")),
            "flight_category": (row.get("flight_category") or "").strip() or None,
            "metar_type": (row.get("metar_type") or "").strip() or None,
            "raw_json": {k: v for k, v in row.items() if v not in (None, "")},
        })
    return out


def parse_tafs_xml(body: bytes) -> list[dict]:
    """解析 tafs.cache.xml.gz。根节点 <response><data><TAF>...</TAF></data></response>。"""
    text = _decompress(body)
    root = ET.fromstring(text)

    out: list[dict] = []
    for taf in root.iter("TAF"):
        raw = (taf.findtext("raw_text") or "").strip()
        icao = (taf.findtext("station_id") or "").strip().upper()
        if not icao or not raw:
            continue
        forecasts: list[dict] = []
        for fcst in taf.findall("forecast"):
            forecasts.append({child.tag: _xml_value(child) for child in fcst})
        out.append({
            "icao": icao,
            "source_code": SOURCE_CODE,
            "issue_time": (taf.findtext("issue_time") or "").strip() or None,
            "valid_from": (taf.findtext("valid_time_from") or "").strip() or None,
            "valid_to": (taf.findtext("valid_time_to") or "").strip() or None,
            "raw_text": raw,
            "raw_json": {
                "bulletin_time": taf.findtext("bulletin_time"),
                "latitude": taf.findtext("latitude"),
                "longitude": taf.findtext("longitude"),
                "elevation_m": taf.findtext("elevation_m"),
                "forecasts": forecasts,
            },
        })
    return out


def _xml_value(elem: ET.Element) -> Any:
    """叶子节点：取文本；带属性的节点：合并属性和文本到 dict。"""
    if list(elem):
        return [{"tag": c.tag, **c.attrib, "text": (c.text or "").strip()} for c in elem]
    text = (elem.text or "").strip()
    if elem.attrib:
        return {**elem.attrib, "text": text} if text else dict(elem.attrib)
    return text or None
