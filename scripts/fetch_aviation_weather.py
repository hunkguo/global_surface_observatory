"""批量抓取 METAR + TAF，并把统一 JSON 写到 shared_data/。

写库由后续 sync_aviation_to_sqlite.py 负责；本脚本只产出 JSON。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources import awc_client, avwx_client
from storage.sqlite_repo import DATA_ROOT, DEFAULT_DB_PATH, connection

try:  # .env 可选
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_LATEST = DATA_ROOT / "shared_data" / "aviation_weather_latest.json"
HISTORY_DIR = DATA_ROOT / "shared_data" / "aviation_weather_history"

CLIENTS = {
    "awc": awc_client,
    "avwx": avwx_client,
}


def _load_icaos_from_db(db_path: str, limit: int = 0, country: str | None = None) -> list[str]:
    with connection(db_path) as conn:
        sql = "SELECT icao FROM airports"
        params: list = []
        if country:
            sql += " WHERE country = ?"
            params.append(country.upper())
        sql += " ORDER BY icao"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [row[0] for row in conn.execute(sql, params)]


def _fetch_source(source: str, icaos: list[str]) -> tuple[list[dict], list[dict]]:
    client = CLIENTS[source]
    metars = client.fetch_metars(icaos)
    tafs = client.fetch_tafs(icaos)
    return metars, tafs


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch METAR + TAF for ICAOs.")
    parser.add_argument("--icaos", help="逗号分隔 ICAO；缺省从 airports 表读")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--country", default=None, help="按国家过滤 airports 表")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sources", default="awc", help="逗号分隔：awc,avwx")
    parser.add_argument("--out", default=str(DEFAULT_LATEST))
    parser.add_argument("--save-history", action="store_true", help="同时落盘到 history 目录")
    args = parser.parse_args()

    if args.icaos:
        icaos = [s.strip().upper() for s in args.icaos.split(",") if s.strip()]
    else:
        icaos = _load_icaos_from_db(args.db, args.limit, args.country)
    if not icaos:
        print("[fetch_aviation_weather] no ICAO to query", file=sys.stderr)
        return 1

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = set(sources) - CLIENTS.keys()
    if unknown:
        print(f"[fetch_aviation_weather] unknown sources: {unknown}", file=sys.stderr)
        return 2

    print(f"[fetch_aviation_weather] {len(icaos)} stations × {sources}")

    run_started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metars: list[dict] = []
    tafs: list[dict] = []
    errors: list[dict] = []
    for src in sources:
        t0 = time.time()
        try:
            m, t = _fetch_source(src, icaos)
        except avwx_client.AvwxConfigError as exc:
            errors.append({"source": src, "error": str(exc)})
            print(f"[fetch_aviation_weather] skip {src}: {exc}", file=sys.stderr)
            continue
        except Exception as exc:
            errors.append({"source": src, "error": repr(exc)})
            print(f"[fetch_aviation_weather] {src} failed: {exc}", file=sys.stderr)
            continue
        metars.extend(m)
        tafs.extend(t)
        print(f"  {src:>5}: {len(m)} metars, {len(t)} tafs ({time.time()-t0:.1f}s)")

    payload = {
        "run_started_at": run_started,
        "run_finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requested_icaos": icaos,
        "sources": sources,
        "metars": metars,
        "tafs": tafs,
        "errors": errors,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fetch_aviation_weather] wrote {out}  ({len(metars)} metars, {len(tafs)} tafs)")

    if args.save_history:
        day = run_started[:10]
        hist_dir = HISTORY_DIR / day
        hist_dir.mkdir(parents=True, exist_ok=True)
        hist_file = hist_dir / f"{run_started.replace(':', '-')}.json"
        hist_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[fetch_aviation_weather] history -> {hist_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
