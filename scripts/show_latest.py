"""按 ICAO 查询最新 METAR / TAF（同时显示 UTC 与机场所在时区的本地时间）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.time_utils import fmt_local, tz_of
from parsers.units import fmt_temp_cf
from storage.sqlite_repo import DEFAULT_DB_PATH, connection


AIRPORT_SQL = "SELECT latitude, longitude, name, city, country FROM airports WHERE icao = ?"

METAR_SQL = """
SELECT icao, source_code, observation_time, metar_type,
       temperature_c, dewpoint_c, wind_dir, wind_speed, gust,
       visibility, altimeter, flight_category, raw_text
FROM metar_reports
WHERE icao = ?
ORDER BY observation_time DESC
LIMIT 1
"""

TAF_SQL = """
SELECT icao, source_code, issue_time, valid_from, valid_to, raw_text
FROM taf_reports
WHERE icao = ?
ORDER BY issue_time DESC
LIMIT 1
"""


def _ts_with_local(iso: str | None, tz_name: str | None) -> str:
    """'2026-04-19T02:00:00.000Z' -> '2026-04-19T02:00:00.000Z (2026-04-19 11:00 JST)'。"""
    if not iso:
        return "-"
    if not tz_name:
        return iso
    return f"{iso} ({fmt_local(iso, tz_name)})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show latest METAR / TAF per ICAO.")
    parser.add_argument("icaos", nargs="+", help="一个或多个 ICAO 代码")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()

    with connection(args.db) as conn:
        for icao in (s.upper() for s in args.icaos):
            ap = conn.execute(AIRPORT_SQL, (icao,)).fetchone()
            tz_name = tz_of(ap["latitude"], ap["longitude"]) if ap else None
            m = conn.execute(METAR_SQL, (icao,)).fetchone()
            t = conn.execute(TAF_SQL, (icao,)).fetchone()

            header = f"=== {icao} ==="
            if ap and ap["name"]:
                header += f"  {ap['name']}"
            if tz_name:
                header += f"  ({tz_name})"
            print(header)

            if m:
                print(
                    f"  METAR [{_ts_with_local(m['observation_time'], tz_name)}] {m['metar_type']}  "
                    f"T={fmt_temp_cf(m['temperature_c'])}  Td={fmt_temp_cf(m['dewpoint_c'])}  "
                    f"wind={m['wind_dir']}°/{m['wind_speed']}kt gust={m['gust']}  "
                    f"vis={m['visibility']}  QNH={m['altimeter']}hPa  cat={m['flight_category']}"
                )
                print(f"    raw: {m['raw_text']}")
            else:
                print("  METAR: (no data)")
            if t:
                print(f"  TAF   [{_ts_with_local(t['issue_time'], tz_name)}]")
                print(f"        valid {_ts_with_local(t['valid_from'], tz_name)}")
                print(f"           -> {_ts_with_local(t['valid_to'], tz_name)}")
                print(f"    raw: {t['raw_text']}")
            else:
                print("  TAF  : (no data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
