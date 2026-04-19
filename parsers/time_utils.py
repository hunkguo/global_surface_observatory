"""时区解析与本地时间格式化。

用 timezonefinder 离线把 (lat, lon) 解到 IANA tz 名称，
然后用 stdlib zoneinfo 计算本地时间（含 DST）。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from timezonefinder import TimezoneFinder
    _tf: TimezoneFinder | None = TimezoneFinder()
except Exception:
    _tf = None


def tz_of(lat: float | None, lon: float | None) -> str | None:
    """(lat, lon) -> IANA 时区名。失败返回 None。"""
    if _tf is None or lat is None or lon is None:
        return None
    try:
        return _tf.timezone_at(lng=lon, lat=lat)
    except Exception:
        return None


def parse_iso_utc(iso: str | None) -> datetime | None:
    """解析 '2026-04-19T02:00:00.000Z' / '2026-04-19T02:00:00Z' / 带偏移的 ISO。"""
    if not iso:
        return None
    s = iso.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def to_local(iso_utc: str | None, tz_name: str | None) -> datetime | None:
    if not tz_name:
        return None
    dt = parse_iso_utc(iso_utc)
    if dt is None:
        return None
    try:
        return dt.astimezone(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        return None


def fmt_local(iso_utc: str | None, tz_name: str | None, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    """格式化为本地时间字符串，例如 '2026-04-19 11:00 JST'。无法解析时返回 '-'。"""
    local = to_local(iso_utc, tz_name)
    return local.strftime(fmt) if local else "-"


def fmt_local_short(iso_utc: str | None, tz_name: str | None) -> str:
    """精简格式 'HH:MM tz'，便于在表格里和 UTC 时间并列。"""
    local = to_local(iso_utc, tz_name)
    return local.strftime("%H:%M") if local else "-"
