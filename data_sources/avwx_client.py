"""AVWX 客户端（需要 AVWX_API_KEY 环境变量）。"""
from __future__ import annotations

import os

import requests

from parsers import metar_parser, taf_parser

AVWX_BASE = "https://avwx.rest/api"
SOURCE_CODE = "avwx"


class AvwxConfigError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    key = os.environ.get("AVWX_API_KEY")
    if not key:
        raise AvwxConfigError("AVWX_API_KEY not set")
    return {"Authorization": f"Token {key}"}


def _get(endpoint: str, icao: str, timeout: float) -> dict | None:
    resp = requests.get(
        f"{AVWX_BASE}/{endpoint}/{icao}",
        headers=_headers(),
        timeout=timeout,
    )
    if resp.status_code in (404, 400):
        return None
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else None


def fetch_metars(icaos: list[str], timeout: float = 20.0) -> list[dict]:
    out: list[dict] = []
    for icao in icaos:
        try:
            data = _get("metar", icao, timeout)
        except AvwxConfigError:
            raise
        except Exception:
            continue
        if not data or not data.get("raw"):
            continue
        out.append({**metar_parser.from_avwx(data), "source_code": SOURCE_CODE, "raw_json": data})
    return out


def fetch_tafs(icaos: list[str], timeout: float = 20.0) -> list[dict]:
    out: list[dict] = []
    for icao in icaos:
        try:
            data = _get("taf", icao, timeout)
        except AvwxConfigError:
            raise
        except Exception:
            continue
        if not data or not data.get("raw"):
            continue
        out.append({**taf_parser.from_avwx(data), "source_code": SOURCE_CODE, "raw_json": data})
    return out
