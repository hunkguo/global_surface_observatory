"""Aviation Weather Center (AWC) 官方数据客户端。"""
from __future__ import annotations

from typing import Iterable

import requests

from parsers import metar_parser, taf_parser

AWC_BASE = "https://aviationweather.gov/api/data"
SOURCE_CODE = "awc"
BATCH_SIZE = 100  # 批量 ICAO 查询的上限


def _chunks(seq: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _get_json(endpoint: str, icaos: list[str], timeout: float) -> list[dict]:
    if not icaos:
        return []
    out: list[dict] = []
    for batch in _chunks(icaos, BATCH_SIZE):
        resp = requests.get(
            f"{AWC_BASE}/{endpoint}",
            params={"ids": ",".join(batch), "format": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json() or []
        if isinstance(data, list):
            out.extend(data)
    return out


def fetch_metars(icaos: list[str], timeout: float = 30.0) -> list[dict]:
    items = _get_json("metar", icaos, timeout)
    return [
        {**metar_parser.from_awc(item), "source_code": SOURCE_CODE, "raw_json": item}
        for item in items
        if item.get("rawOb")
    ]


def fetch_tafs(icaos: list[str], timeout: float = 30.0) -> list[dict]:
    items = _get_json("taf", icaos, timeout)
    return [
        {**taf_parser.from_awc(item), "source_code": SOURCE_CODE, "raw_json": item}
        for item in items
        if (item.get("rawTAF") or item.get("rawOb"))
    ]
