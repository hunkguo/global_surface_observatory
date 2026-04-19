"""初始化 GSO SQLite 数据库：创建表结构 + 灌入默认 weather_sources。"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.sqlite_repo import DEFAULT_DB_PATH, apply_schema, connection

DEFAULT_SOURCES = [
    ("awc",   "Aviation Weather Center", "https://aviationweather.gov/api/data"),
    ("avwx",  "AVWX",                    "https://avwx.rest/api"),
]

# 老版 schema 升级：列名 -> SQL 片段
METAR_REPORTS_MIGRATIONS = {
    "metar_type":            "ALTER TABLE metar_reports ADD COLUMN metar_type TEXT",
    "sea_level_pressure_mb": "ALTER TABLE metar_reports ADD COLUMN sea_level_pressure_mb REAL",
}


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_in_place(conn: sqlite3.Connection) -> list[str]:
    """对已存在的老库补缺列。返回执行过的迁移语句。"""
    applied: list[str] = []
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metar_reports'"
    ).fetchone()
    if exists:
        cols = _existing_columns(conn, "metar_reports")
        for col, sql in METAR_REPORTS_MIGRATIONS.items():
            if col not in cols:
                conn.execute(sql)
                applied.append(sql)
    return applied


def seed_weather_sources(conn) -> None:
    conn.executemany(
        """
        INSERT INTO weather_sources (source_code, source_name, base_url, enabled)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(source_code) DO UPDATE SET
            source_name = excluded.source_name,
            base_url    = excluded.base_url
        """,
        DEFAULT_SOURCES,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize GSO SQLite database.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 文件路径")
    args = parser.parse_args()

    db_path = Path(args.db)
    with connection(db_path) as conn:
        migrated = migrate_in_place(conn)
        apply_schema(conn)
        seed_weather_sources(conn)

    print(f"[init_aviation_db] schema applied at {db_path}")
    for stmt in migrated:
        print(f"[init_aviation_db] migrated: {stmt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
