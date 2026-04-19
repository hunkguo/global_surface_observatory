"""拉取全球机场主数据：写入 shared_data/airports.json 并 upsert 到 airports 表。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources.airport_codes_client import fetch_airports
from storage.sqlite_repo import DATA_ROOT, DEFAULT_DB_PATH, connection, upsert_airport

DEFAULT_JSON_PATH = DATA_ROOT / "shared_data" / "airports.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch global airport codes (OurAirports).")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 文件路径")
    parser.add_argument("--json", default=str(DEFAULT_JSON_PATH), help="JSON 输出路径")
    parser.add_argument("--limit", type=int, default=0, help="(调试) 仅保留前 N 条")
    parser.add_argument("--country", default=None, help="仅保留指定 ISO 国家代码（如 CN/US）")
    args = parser.parse_args()

    t0 = time.time()
    records = list(fetch_airports())
    if args.country:
        records = [r for r in records if r.country == args.country.upper()]
    if args.limit:
        records = records[: args.limit]
    print(f"[fetch_airport_codes] {len(records)} airports (elapsed {time.time()-t0:.1f}s)")

    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[fetch_airport_codes] wrote {json_path}")

    with connection(args.db) as conn:
        for r in records:
            upsert_airport(conn, asdict(r))
    print(f"[fetch_airport_codes] upserted into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
