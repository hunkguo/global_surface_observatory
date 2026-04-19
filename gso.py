"""GSO 统一 CLI 入口。打包 exe 时以此为主脚本。

用法：
    gso init                       # 创建/迁移 SQLite
    gso fetch-airports             # 从 OurAirports 灌全球机场代码
    gso poll                       # 单次抓 AWC 缓存并增量写库（外部调度使用）
    gso poll --loop 60             # 内置 60s 循环（开发/调试）
    gso fetch --icaos RJTT,ZBAA    # 用 API 精确查几个机场
    gso show RJTT ZBAA             # 按 ICAO 打印最新 METAR/TAF

数据目录：默认 cwd/db 与 cwd/shared_data。
         可用环境变量 GSO_DATA_DIR 或子命令 --db 参数覆盖。
"""
from __future__ import annotations

import importlib
import sys

COMMANDS: dict[str, tuple[str, str]] = {
    "init":           ("scripts.init_aviation_db",      "创建/迁移 SQLite 数据库"),
    "fetch-airports": ("scripts.fetch_airport_codes",   "下载 OurAirports 全球机场代码"),
    "poll":           ("scripts.poll_aviation_weather", "抓 AWC 缓存并增量写库（主抓路径）"),
    "fetch":          ("scripts.fetch_aviation_weather","按 ICAO 用 API 精确查 METAR/TAF"),
    "show":           ("scripts.show_latest",           "按 ICAO 打印最新 METAR/TAF"),
}


def _print_help() -> None:
    print("GSO - Global Surface Observatory")
    print()
    print("Usage: gso <command> [options]")
    print()
    print("Commands:")
    width = max(len(c) for c in COMMANDS)
    for name, (_mod, desc) in COMMANDS.items():
        print(f"  {name:<{width}}  {desc}")
    print()
    print("Run 'gso <command> --help' for command-specific options.")
    print("Data dir defaults to current working directory; override via GSO_DATA_DIR.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"gso: unknown command '{cmd}'\n", file=sys.stderr)
        _print_help()
        return 2
    module_name, _ = COMMANDS[cmd]
    mod = importlib.import_module(module_name)
    sys.argv = [f"gso {cmd}", *rest]
    return int(mod.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
