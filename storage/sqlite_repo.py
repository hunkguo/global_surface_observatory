"""SQLite 连接与基础读写封装。"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


def _resource_root() -> Path:
    """只读资源（schema.sql 等）所在目录。frozen 时来自 PyInstaller 的 _MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def _data_root() -> Path:
    """可写数据目录（db/, shared_data/）。可用 GSO_DATA_DIR 覆盖，默认 cwd。"""
    env = os.environ.get("GSO_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.cwd()


RESOURCE_ROOT = _resource_root()
DATA_ROOT = _data_root()
DEFAULT_DB_PATH = DATA_ROOT / "db" / "aviation_weather.db"
SCHEMA_PATH = RESOURCE_ROOT / "storage" / "sqlite_schema.sql"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def connection(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_schema(conn: sqlite3.Connection, schema_path: Path = SCHEMA_PATH) -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    conn.executescript(sql)


def upsert_airport(conn: sqlite3.Connection, airport: dict) -> None:
    conn.execute(
        """
        INSERT INTO airports (icao, iata, name, city, country, latitude, longitude,
                              elevation_ft, timezone, source, updated_at)
        VALUES (:icao, :iata, :name, :city, :country, :latitude, :longitude,
                :elevation_ft, :timezone, :source, CURRENT_TIMESTAMP)
        ON CONFLICT(icao) DO UPDATE SET
            iata         = excluded.iata,
            name         = excluded.name,
            city         = excluded.city,
            country      = excluded.country,
            latitude     = excluded.latitude,
            longitude    = excluded.longitude,
            elevation_ft = excluded.elevation_ft,
            timezone     = excluded.timezone,
            source       = excluded.source,
            updated_at   = CURRENT_TIMESTAMP
        """,
        airport,
    )


# --- HTTP 条件 GET 缓存状态 --------------------------------------------------

def get_cache_state(conn: sqlite3.Connection, url: str) -> dict | None:
    row = conn.execute(
        "SELECT url, etag, last_modified, last_fetched_at, last_status "
        "FROM http_cache_state WHERE url = ?",
        (url,),
    ).fetchone()
    return dict(row) if row else None


def save_cache_state(
    conn: sqlite3.Connection,
    url: str,
    etag: str | None,
    last_modified: str | None,
    status: int,
) -> None:
    conn.execute(
        """
        INSERT INTO http_cache_state (url, etag, last_modified, last_fetched_at, last_status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            etag            = excluded.etag,
            last_modified   = excluded.last_modified,
            last_fetched_at = excluded.last_fetched_at,
            last_status     = excluded.last_status
        """,
        (url, etag, last_modified, _now_iso(), status),
    )


# --- 抓取任务记录 ------------------------------------------------------------

def start_fetch_run(conn: sqlite3.Connection, run_type: str) -> int:
    cur = conn.execute(
        "INSERT INTO fetch_runs (run_type, started_at, status) VALUES (?, ?, 'running')",
        (run_type, _now_iso()),
    )
    return int(cur.lastrowid)


def finish_fetch_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    total_stations: int = 0,
    success_count: int = 0,
    fail_count: int = 0,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE fetch_runs
        SET finished_at    = ?,
            status         = ?,
            total_stations = ?,
            success_count  = ?,
            fail_count     = ?,
            error_message  = ?
        WHERE id = ?
        """,
        (_now_iso(), status, total_stations, success_count, fail_count, error_message, run_id),
    )


# --- METAR / TAF 增量游标 + 写入 ---------------------------------------------

def load_metar_cursor(conn: sqlite3.Connection, source_code: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT icao, MAX(observation_time) AS t FROM metar_reports "
        "WHERE source_code = ? AND observation_time IS NOT NULL GROUP BY icao",
        (source_code,),
    ).fetchall()
    return {r["icao"]: r["t"] for r in rows if r["t"]}


def load_taf_cursor(conn: sqlite3.Connection, source_code: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT icao, MAX(issue_time) AS t FROM taf_reports "
        "WHERE source_code = ? AND issue_time IS NOT NULL GROUP BY icao",
        (source_code,),
    ).fetchall()
    return {r["icao"]: r["t"] for r in rows if r["t"]}


_METAR_INSERT_SQL = """
INSERT OR IGNORE INTO metar_reports (
    fetch_run_id, icao, source_code, observation_time, raw_text, sanitized_text,
    temperature_c, dewpoint_c, wind_dir, wind_speed, gust, visibility,
    altimeter, sea_level_pressure_mb, flight_category, metar_type, raw_json
) VALUES (
    :fetch_run_id, :icao, :source_code, :observation_time, :raw_text, :sanitized_text,
    :temperature_c, :dewpoint_c, :wind_dir, :wind_speed, :gust, :visibility,
    :altimeter, :sea_level_pressure_mb, :flight_category, :metar_type, :raw_json
)
"""


def insert_metars(conn: sqlite3.Connection, rows: Iterable[dict], fetch_run_id: int) -> int:
    payload = []
    for r in rows:
        payload.append({
            "fetch_run_id": fetch_run_id,
            "icao": r.get("icao"),
            "source_code": r.get("source_code"),
            "observation_time": r.get("observation_time"),
            "raw_text": r.get("raw_text"),
            "sanitized_text": r.get("sanitized_text"),
            "temperature_c": r.get("temperature_c"),
            "dewpoint_c": r.get("dewpoint_c"),
            "wind_dir": r.get("wind_dir"),
            "wind_speed": r.get("wind_speed"),
            "gust": r.get("gust"),
            "visibility": r.get("visibility"),
            "altimeter": r.get("altimeter"),
            "sea_level_pressure_mb": r.get("sea_level_pressure_mb"),
            "flight_category": r.get("flight_category"),
            "metar_type": r.get("metar_type"),
            "raw_json": _dumps(r.get("raw_json")),
        })
    if not payload:
        return 0
    before = conn.total_changes
    conn.executemany(_METAR_INSERT_SQL, payload)
    return conn.total_changes - before


_TAF_INSERT_SQL = """
INSERT OR IGNORE INTO taf_reports (
    fetch_run_id, icao, source_code, issue_time, valid_from, valid_to,
    raw_text, raw_json
) VALUES (
    :fetch_run_id, :icao, :source_code, :issue_time, :valid_from, :valid_to,
    :raw_text, :raw_json
)
"""


def insert_tafs(conn: sqlite3.Connection, rows: Iterable[dict], fetch_run_id: int) -> int:
    payload = []
    for r in rows:
        payload.append({
            "fetch_run_id": fetch_run_id,
            "icao": r.get("icao"),
            "source_code": r.get("source_code"),
            "issue_time": r.get("issue_time"),
            "valid_from": r.get("valid_from"),
            "valid_to": r.get("valid_to"),
            "raw_text": r.get("raw_text"),
            "raw_json": _dumps(r.get("raw_json")),
        })
    if not payload:
        return 0
    before = conn.total_changes
    conn.executemany(_TAF_INSERT_SQL, payload)
    return conn.total_changes - before


# --- helpers -----------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dumps(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
