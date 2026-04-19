"""按 ICAO 查询最新 METAR / TAF。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage.sqlite_repo import DEFAULT_DB_PATH, connection


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Show latest METAR / TAF per ICAO.")
    parser.add_argument("icaos", nargs="+", help="一个或多个 ICAO 代码")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()

    with connection(args.db) as conn:
        for icao in (s.upper() for s in args.icaos):
            m = conn.execute(METAR_SQL, (icao,)).fetchone()
            t = conn.execute(TAF_SQL, (icao,)).fetchone()
            print(f"=== {icao} ===")
            if m:
                print(
                    f"  METAR [{m['observation_time']}] {m['metar_type']}  "
                    f"T={m['temperature_c']}°C  Td={m['dewpoint_c']}°C  "
                    f"wind={m['wind_dir']}°/{m['wind_speed']}kt gust={m['gust']}  "
                    f"vis={m['visibility']}  QNH={m['altimeter']}hPa  cat={m['flight_category']}"
                )
                print(f"    raw: {m['raw_text']}")
            else:
                print("  METAR: (no data)")
            if t:
                print(f"  TAF   [{t['issue_time']}] valid {t['valid_from']} -> {t['valid_to']}")
                print(f"    raw: {t['raw_text']}")
            else:
                print("  TAF  : (no data)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
