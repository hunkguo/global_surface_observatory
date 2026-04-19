"""OurAirports CSV 拉取与清洗。

OurAirports 数据由作者 David Megginson 以公有领域发布，字段说明见：
https://ourairports.com/help/data-dictionary.html
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Iterator

import requests

OURAIRPORTS_CSV_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
SOURCE_CODE = "ourairports"
EXCLUDED_TYPES = {"closed"}


@dataclass
class AirportRecord:
    icao: str
    iata: str | None
    name: str
    city: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    elevation_ft: float | None
    timezone: str | None
    source: str


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _pick_icao(row: dict) -> str | None:
    """gps_code 优先（OurAirports 里 gps_code 一定是 ICAO），ident 作 4 字母字母兜底。"""
    code = (row.get("gps_code") or "").strip().upper()
    if len(code) == 4 and code.isalpha():
        return code
    ident = (row.get("ident") or "").strip().upper()
    if len(ident) == 4 and ident.isalpha():
        return ident
    return None


def fetch_airports(
    url: str = OURAIRPORTS_CSV_URL,
    timeout: float = 60.0,
) -> Iterator[AirportRecord]:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    seen: set[str] = set()
    for row in reader:
        if (row.get("type") or "").strip() in EXCLUDED_TYPES:
            continue
        icao = _pick_icao(row)
        if not icao or icao in seen:
            continue
        seen.add(icao)
        iata = (row.get("iata_code") or "").strip().upper() or None
        yield AirportRecord(
            icao=icao,
            iata=iata,
            name=(row.get("name") or "").strip(),
            city=(row.get("municipality") or "").strip() or None,
            country=(row.get("iso_country") or "").strip().upper() or None,
            latitude=_to_float(row.get("latitude_deg")),
            longitude=_to_float(row.get("longitude_deg")),
            elevation_ft=_to_float(row.get("elevation_ft")),
            timezone=None,
            source=SOURCE_CODE,
        )
