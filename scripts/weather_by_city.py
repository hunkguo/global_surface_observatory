"""城市名 -> 附近机场 -> 最近 N 小时 METAR 温度汇总。

流程：
  city -> Nominatim geocode -> (lat, lon)
       -> airports 表按边界框预筛 + Haversine 精算取 top-N
       -> metar_reports 按 ICAO 在时间窗内做 MIN/MAX 聚合
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources.geocode_client import geocode
from storage.sqlite_repo import DEFAULT_DB_PATH, connection

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    la1, lo1, la2, lo2 = map(radians, (lat1, lon1, lat2, lon2))
    dl = la2 - la1
    dlo = lo2 - lo1
    a = sin(dl / 2) ** 2 + cos(la1) * cos(la2) * sin(dlo / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def find_nearby_airports(
    conn: sqlite3.Connection,
    lat: float,
    lon: float,
    radius_km: float,
    top: int,
) -> list[tuple[float, dict]]:
    """边界框预筛 + Haversine 精算，返回 [(distance_km, airport_row), ...]。"""
    dlat = radius_km / 111.0
    cos_lat = max(abs(cos(radians(lat))), 0.1)
    dlon = radius_km / (111.0 * cos_lat)
    rows = conn.execute(
        """
        SELECT icao, iata, name, city, country, latitude, longitude, elevation_ft
        FROM airports
        WHERE latitude  IS NOT NULL
          AND longitude IS NOT NULL
          AND latitude  BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
        """,
        (lat - dlat, lat + dlat, lon - dlon, lon + dlon),
    ).fetchall()
    out: list[tuple[float, dict]] = []
    for r in rows:
        d = haversine_km(lat, lon, r["latitude"], r["longitude"])
        if d <= radius_km:
            out.append((d, dict(r)))
    out.sort(key=lambda x: x[0])
    return out[:top]


def airport_temperature_stats(
    conn: sqlite3.Connection, icao: str, since_iso: str
) -> dict:
    row = conn.execute(
        """
        SELECT MIN(temperature_c) AS t_min,
               MAX(temperature_c) AS t_max,
               MIN(observation_time) AS first_obs,
               MAX(observation_time) AS last_obs,
               COUNT(*) AS n
        FROM metar_reports
        WHERE icao = ?
          AND observation_time >= ?
          AND temperature_c IS NOT NULL
        """,
        (icao, since_iso),
    ).fetchone()
    return dict(row) if row else {
        "t_min": None, "t_max": None, "first_obs": None, "last_obs": None, "n": 0,
    }


def _fmt_temp(v) -> str:
    return f"{v:>5.1f}" if v is not None else "   -- "


def _fmt_time_short(t: str | None) -> str:
    if not t:
        return "-"
    return t.replace("T", " ")[:16]  # '2026-04-19 03:00'


def _print_city_block(
    label: str,
    loc_display: str,
    lat: float,
    lon: float,
    since_iso: str,
    now_iso: str,
    hours: int,
    rows: list[tuple[float, dict]],
    conn: sqlite3.Connection,
    radius_km: float,
) -> None:
    print(f"=== {label} ===")
    print(f"  Location : {loc_display}")
    print(f"  Coords   : ({lat:.4f}, {lon:.4f})")
    print(f"  Window   : {since_iso}  ->  {now_iso}  (last {hours}h, UTC)")
    print()
    if not rows:
        print(f"  (no airports within {radius_km:.0f}km — run `gso fetch-airports` to load globally)")
        print()
        return
    header = f"  {'ICAO':<6} {'Name':<38} {'Dist':>8}  {'Tmax':>6}  {'Tmin':>6}  {'N':>4}  Latest"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for dist, a in rows:
        stats = airport_temperature_stats(conn, a["icao"], since_iso)
        name = (a["name"] or "")[:38]
        print(
            f"  {a['icao']:<6} {name:<38} "
            f"{dist:>6.1f}km  {_fmt_temp(stats['t_max'])}  {_fmt_temp(stats['t_min'])}  "
            f"{stats['n']:>4}  {_fmt_time_short(stats['last_obs'])}"
        )
    print()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        description="按城市名查附近机场最近 N 小时温度。"
    )
    parser.add_argument("cities", nargs="+", help="一个或多个城市名（中英文均可）")
    parser.add_argument("--radius", type=float, default=100.0, help="搜索半径 km，默认 100")
    parser.add_argument("--hours", type=int, default=24, help="时间窗（小时），默认 24")
    parser.add_argument("--top", type=int, default=3, help="每城市最多显示机场数，默认 3")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)

    now_dt = datetime.now(timezone.utc)
    since_iso = (now_dt - timedelta(hours=args.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    with connection(args.db) as conn:
        for city in args.cities:
            loc = geocode(city)
            if not loc:
                print(f"=== {city} ===")
                print("  (geocoding failed — 城市未找到或网络异常)")
                print()
                continue
            rows = find_nearby_airports(conn, loc.lat, loc.lon, args.radius, args.top)
            _print_city_block(
                city, loc.display_name, loc.lat, loc.lon,
                since_iso, now_iso, args.hours, rows, conn, args.radius,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
