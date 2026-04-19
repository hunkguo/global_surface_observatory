"""每分钟轮询 AWC 缓存包 -> 增量写入 SQLite。

单次模式（默认）：幂等执行一次，交给外部调度（Windows 任务计划 / cron / systemd.timer）。
循环模式：--loop N 在进程内每 N 秒重复一次，用于开发调试。

策略：
- 条件 GET (If-None-Match / If-Modified-Since)，304 直接走空操作 + 记一行 fetch_runs
- cursor[icao] = MAX(observation_time) per ICAO；只插入严格大于 cursor 的观测
- INSERT OR IGNORE 兜底 UNIQUE 约束（防多实例并发 / 同时刻多种报文类型边界情况）
- 任何一轮失败只影响当轮，不影响循环
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_sources import awc_cache_client as cache
from storage.sqlite_repo import (
    DEFAULT_DB_PATH,
    connection,
    finish_fetch_run,
    get_cache_state,
    insert_metars,
    insert_tafs,
    load_metar_cursor,
    load_taf_cursor,
    save_cache_state,
    start_fetch_run,
)


def _newer(item: dict, cursor: dict[str, str], time_key: str) -> bool:
    t = item.get(time_key)
    if not t:
        return False
    last = cursor.get(item["icao"])
    return last is None or t > last


def _poll_metar(conn, verbose: bool) -> None:
    url = cache.METAR_CACHE_URL
    state = get_cache_state(conn, url) or {}
    run_id = start_fetch_run(conn, "metar_cache")
    try:
        r = cache.download_if_changed(
            url, etag=state.get("etag"), last_modified=state.get("last_modified")
        )
        if r.status == 304:
            save_cache_state(conn, url, r.etag, r.last_modified, 304)
            finish_fetch_run(conn, run_id, "not_modified")
            if verbose:
                print(f"[metar] 304 ({r.elapsed_s:.1f}s)")
            return
        items = cache.parse_metars_csv(r.body)
        cursor = load_metar_cursor(conn, cache.SOURCE_CODE)
        fresh = [x for x in items if _newer(x, cursor, "observation_time")]
        inserted = insert_metars(conn, fresh, run_id)
        save_cache_state(conn, url, r.etag, r.last_modified, 200)
        finish_fetch_run(
            conn, run_id, "ok",
            total_stations=len(items),
            success_count=inserted,
            fail_count=max(len(fresh) - inserted, 0),
        )
        if verbose:
            print(
                f"[metar] 200 parsed={len(items)} fresh={len(fresh)} "
                f"inserted={inserted} ({r.elapsed_s:.1f}s)"
            )
    except Exception as exc:
        finish_fetch_run(conn, run_id, "error", error_message=repr(exc))
        raise


def _poll_taf(conn, verbose: bool) -> None:
    url = cache.TAF_CACHE_URL
    state = get_cache_state(conn, url) or {}
    run_id = start_fetch_run(conn, "taf_cache")
    try:
        r = cache.download_if_changed(
            url, etag=state.get("etag"), last_modified=state.get("last_modified")
        )
        if r.status == 304:
            save_cache_state(conn, url, r.etag, r.last_modified, 304)
            finish_fetch_run(conn, run_id, "not_modified")
            if verbose:
                print(f"[taf] 304 ({r.elapsed_s:.1f}s)")
            return
        items = cache.parse_tafs_xml(r.body)
        cursor = load_taf_cursor(conn, cache.SOURCE_CODE)
        fresh = [x for x in items if _newer(x, cursor, "issue_time")]
        inserted = insert_tafs(conn, fresh, run_id)
        save_cache_state(conn, url, r.etag, r.last_modified, 200)
        finish_fetch_run(
            conn, run_id, "ok",
            total_stations=len(items),
            success_count=inserted,
            fail_count=max(len(fresh) - inserted, 0),
        )
        if verbose:
            print(
                f"[taf] 200 parsed={len(items)} fresh={len(fresh)} "
                f"inserted={inserted} ({r.elapsed_s:.1f}s)"
            )
    except Exception as exc:
        finish_fetch_run(conn, run_id, "error", error_message=repr(exc))
        raise


def poll_once(db_path: str | Path, skip_metar: bool, skip_taf: bool, verbose: bool) -> None:
    with connection(db_path) as conn:
        if not skip_metar:
            _poll_metar(conn, verbose)
        if not skip_taf:
            _poll_taf(conn, verbose)


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll AWC cache -> SQLite incremental.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--loop", type=int, default=0, help="循环间隔（秒），0 = 单次退出")
    parser.add_argument("--skip-metar", action="store_true")
    parser.add_argument("--skip-taf", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    verbose = not args.quiet
    while True:
        try:
            poll_once(args.db, args.skip_metar, args.skip_taf, verbose)
        except Exception as exc:
            print(f"[poll] error: {exc!r}", file=sys.stderr)
            if args.loop <= 0:
                return 1
        if args.loop <= 0:
            return 0
        time.sleep(args.loop)


if __name__ == "__main__":
    raise SystemExit(main())
