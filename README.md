<!-- LANG-SWITCH -->
**中文** | [English](./README.en.md)

# GSO — 全球地面观测台（Global Surface Observatory）

> 采集全球机场的实时航空气象报文（METAR / TAF），落到本地 SQLite，作为后续分析、回测、预警和天气预测市场监控的**数据底座**。

---

## ✨ 特性

- **主抓路径：AWC 缓存包**  
  单次 HTTP 拉取 `metars.cache.csv.gz`（每分钟更新，~234 KB）即可覆盖全球所有在报站点，无需按 ICAO 轮询 API。TAF 用 `tafs.cache.xml.gz`（~300 KB）。
- **条件 GET 304 短路**  
  用上次返回的 `ETag` / `Last-Modified` 做 `If-None-Match` / `If-Modified-Since`；未更新时 <1s 返回，基本不消耗带宽。
- **增量写库**  
  启动时从 DB 加载 `MAX(observation_time) per ICAO` 游标；仅插入 `observation_time` 更新过的行；`UNIQUE(icao, source_code, observation_time, raw_text)` 做最终兜底去重。
- **原始报文 + 标准化字段并存**  
  每条记录同时保存 `raw_text`（原报文）、标准化字段（温度 / 露点 / 风 / 能见度 / 气压 / flight_category）以及完整 `raw_json`，后续随时可重算、交叉验证。
- **API 定点备用路径**  
  同时提供 AWC / AVWX JSON API 客户端，可按 ICAO 清单精确查询单机场，做补漏或专题分析。
- **SPECI 自动识别**  
  `metar_reports.metar_type` 区分 METAR 和 SPECI（特选报文）。
- **单文件 exe 分发**  
  内置 CLI 子命令，PyInstaller 打包 ~25 MB，无需目标机安装 Python。

---

## 🚀 快速开始

### 方式一：使用打包好的 exe（Windows 推荐）

```cmd
:: 1. 下载 dist/gso/ 目录（含 gso.exe 和 _internal/）到任意位置，如 C:\GSO\
cd C:\GSO

:: 2. 初始化数据库（会在 cwd 下创建 db\aviation_weather.db）
gso.exe init

:: 3. 第一次抓包（会拉全量约 4800 METAR + 2700 TAF）
gso.exe poll

:: 4. 查看最新气象报文
gso.exe show RJTT ZBAA KJFK EGLL
```

### 方式二：从源码运行

```bash
# 1. 克隆 + 进目录
git clone https://github.com/hunkguo/global_surface_observatory.git
cd global_surface_observatory

# 2. 建虚拟环境 + 装依赖
python -m venv venv
venv\Scripts\activate              # Windows
# source venv/bin/activate         # Linux/macOS
pip install -r requirements.txt

# 3. 初始化 + 跑一次
python gso.py init
python gso.py poll
python gso.py show RJTT ZBAA
```

---

## 📖 子命令详解

```
gso <command> [options]

  init            创建/迁移 SQLite 数据库
  fetch-airports  下载 OurAirports 全球机场代码（~6 万条）
  poll            抓 AWC 缓存并增量写库（主抓路径）
  fetch           按 ICAO 用 API 精确查 METAR/TAF（定点备用）
  show            按 ICAO 打印最新 METAR/TAF
```

运行 `gso <command> --help` 查看各子命令参数。

### `gso init`

幂等：不存在则建库，已存在则跑缺列迁移（例如旧库补 `metar_type`、`sea_level_pressure_mb` 列）。

### `gso poll`

每次运行：
1. 条件 GET `metars.cache.csv.gz` 和 `tafs.cache.xml.gz`
2. 304 → 记一行 `not_modified` run 就退  
   200 → 解析 + 游标过滤 + `INSERT OR IGNORE` 批写
3. 写 `http_cache_state`（ETag / Last-Modified）和 `fetch_runs`（成功计数）

选项：

| 参数 | 说明 |
| --- | --- |
| `--db PATH` | SQLite 文件路径，默认 `./db/aviation_weather.db` |
| `--loop N` | 进程内每 N 秒循环一次（开发调试用；生产建议外部调度） |
| `--skip-metar` | 本轮跳过 METAR |
| `--skip-taf` | 本轮跳过 TAF |
| `--quiet` | 静默模式（无日志） |

### `gso fetch`

按 ICAO 清单用 API 精确查（备用路径）。

```bash
gso fetch --icaos RJTT,ZBAA,KJFK --sources awc
gso fetch --country CN --limit 20 --sources awc,avwx
```

使用 AVWX 需设置环境变量 `AVWX_API_KEY`（在 [avwx.rest](https://avwx.rest/) 注册免费获取）。

### `gso show`

快速查一个或多个 ICAO 的最新 METAR + TAF：

```bash
gso show RJTT                      # 单机场
gso show RJTT ZBAA KJFK EGLL LFPG  # 多机场
```

### `gso fetch-airports`

从 OurAirports 公开 CSV 拉全球机场主数据，灌到 `airports` 表并导出 `shared_data/airports.json`。

```bash
gso fetch-airports                    # 全球（~6 万条）
gso fetch-airports --country CN       # 仅中国
gso fetch-airports --limit 100        # 调试用
```

---

## ⏰ 定时调度

### Windows 任务计划（推荐）

1. `Win + R` → `taskschd.msc`
2. 创建任务 → 触发器：**按计划**，每 1 分钟
3. 操作：
   - 程序：`C:\GSO\gso.exe`（或 `python.exe`）
   - 参数：`poll --quiet`（Python 方式：`gso.py poll --quiet`）
   - 起始于：`C:\GSO`（重要：决定数据文件位置）

### Linux / macOS cron

```crontab
* * * * * cd /opt/gso && /opt/gso/gso poll --quiet >> /var/log/gso.log 2>&1
```

### 开发调试

直接用内置循环，不走外部调度：

```bash
gso poll --loop 60
```

---

## 🗄️ 数据库结构

文件：`db/aviation_weather.db`（SQLite 3）

| 表名 | 用途 |
| --- | --- |
| `airports` | 全球机场主数据（ICAO / IATA / 城市 / 国家 / 经纬度 / 海拔） |
| `weather_sources` | 数据源定义（`awc` / `avwx`） |
| `fetch_runs` | 每次抓取任务记录（started/finished/status/新增条数） |
| `metar_reports` | METAR + SPECI 原始报文和标准化字段 |
| `taf_reports` | TAF 原始报文和顶层字段 |
| `forecast_segments` | TAF 分段预报（MVP 暂未填充，预留扩展） |
| `http_cache_state` | HTTP 条件 GET 状态（url / etag / last_modified） |

核心字段（`metar_reports`）：

```
icao, source_code, observation_time, raw_text, metar_type (METAR/SPECI),
temperature_c, dewpoint_c, wind_dir, wind_speed, gust, visibility,
altimeter (hPa), sea_level_pressure_mb, flight_category (VFR/MVFR/IFR/LIFR),
raw_json (完整 CSV/API 原字段)

UNIQUE(icao, source_code, observation_time, raw_text)
```

> ⚠️ **单位统一**：`altimeter` 列统一存 hPa。CSV 源给的是 inHg，客户端自动 `×33.86389` 换算。

### 常用查询

```sql
-- 按 ICAO 查最近一小时 METAR
SELECT observation_time, metar_type, temperature_c, wind_dir, wind_speed,
       visibility, flight_category, raw_text
FROM metar_reports
WHERE icao = 'RJTT'
  AND observation_time > datetime('now', '-1 hour')
ORDER BY observation_time DESC;

-- 低能见度（LIFR）的机场
SELECT icao, observation_time, visibility, raw_text
FROM metar_reports
WHERE flight_category = 'LIFR'
  AND observation_time > datetime('now', '-30 minutes');

-- 各源覆盖率
SELECT source_code, COUNT(DISTINCT icao) AS stations, COUNT(*) AS reports
FROM metar_reports GROUP BY source_code;
```

---

## 🌐 数据源

| 源 | 类型 | 角色 | 频率 / 限制 |
| --- | --- | --- | --- |
| [AWC `metars.cache.csv.gz`](https://aviationweather.gov/data/cache/metars.cache.csv.gz) | 批量 CSV | METAR 主 | 每分钟更新 |
| [AWC `tafs.cache.xml.gz`](https://aviationweather.gov/data/cache/tafs.cache.xml.gz) | 批量 XML | TAF 主 | 每分钟更新 |
| [AWC API](https://aviationweather.gov/api/data/metar) | JSON 接口 | 定点查询备用 | 100 次/分钟、400 条/次 |
| [AVWX API](https://avwx.rest/) | JSON 接口 | 备用聚合源 | 需 API Key |
| [OurAirports](https://ourairports.com/data/) | CSV | 机场主数据 | 公有领域 |

> 若后续要覆盖非机场地面站，可加入 [NOAA ISD-lite](https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/)（全球 3.5 万+ 站，`deepseek.md` 有方案对比）。

---

## 🏗️ 从源码打包 exe

```bash
# 1. 装构建依赖
pip install -r requirements-dev.txt

# 2. 用现有 spec 文件（最省事）
pyinstaller gso.spec

# 产物：dist/gso/gso.exe  + dist/gso/_internal/
```

也可以从头重建 spec：

```bash
pyinstaller --noconfirm --clean --onedir --name gso ^
  --add-data "storage/sqlite_schema.sql;storage" ^
  --hidden-import scripts.init_aviation_db ^
  --hidden-import scripts.fetch_airport_codes ^
  --hidden-import scripts.poll_aviation_weather ^
  --hidden-import scripts.fetch_aviation_weather ^
  --hidden-import scripts.show_latest ^
  --exclude-module tkinter ^
  gso.py
```

`--onefile` 变体更小更便携，但每次启动要解压到临时目录，不适合每分钟 poll。

---

## 📁 项目结构

```
global_surface_observatory/
├── gso.py                            # CLI 统一入口（打包主脚本）
├── gso.spec                          # PyInstaller 构建配置
├── requirements.txt                  # 运行期依赖
├── requirements-dev.txt              # 打包期依赖（pyinstaller）
│
├── data_sources/
│   ├── awc_cache_client.py           # 主路径：CSV/XML + 条件 GET
│   ├── awc_client.py                 # 备用：AWC JSON API
│   ├── avwx_client.py                # 备用：AVWX JSON API
│   └── airport_codes_client.py       # OurAirports CSV
│
├── parsers/
│   ├── metar_parser.py               # API 模式 METAR 解析
│   └── taf_parser.py                 # API 模式 TAF 解析
│
├── scripts/
│   ├── init_aviation_db.py           # gso init
│   ├── fetch_airport_codes.py        # gso fetch-airports
│   ├── poll_aviation_weather.py      # gso poll（主抓）
│   ├── fetch_aviation_weather.py     # gso fetch（API 备用）
│   └── show_latest.py                # gso show
│
├── storage/
│   ├── sqlite_schema.sql             # 全部建表 DDL
│   └── sqlite_repo.py                # 连接 / 游标 / 写入封装
│
├── db/                               # 运行时生成，不入 git
├── shared_data/                      # 运行时生成，不入 git
├── 机场天气采集项目开发说明书.md     # 原始开发说明书
└── deepseek.md                       # 补充资料（NOAA ISD 等）
```

---

## ⚠️ 已知限制与注意事项

1. **同观测时刻的更正（correction）**  
   游标判断用 `observation_time > cursor`，同一分钟内若到达 CC/AMD 更正报文会被跳过。可改为 `>=` 并依赖 UNIQUE 去重，代价是每次抓全量 INSERT（已有索引兜底，性能影响可接受）。
2. **AWC 缓存仅 ~4800 条 METAR**  
   缓存包涵盖"官方交换"站点，并非全球所有机场。漏报站点需走 API 模式或接入 NOAA ISD。
3. **API 历史回溯仅 15 天**  
   需要长期历史请从 Iowa Environmental Mesonet 或 NOAA ISD 归档。
4. **ICAO ≠ 城市**  
   同城多机场场景不要直接把某机场温度视为城市温度；用于天气预测市场时务必对齐结算规则指定的站点。
5. **altimeter / sea_level_pressure_mb 语义**  
   `altimeter` 是 QNH 修正值（hPa），`sea_level_pressure_mb` 是海平面气压（CSV 源偶尔给）。两者数值相近但不完全相等。

---

## 📚 参考文档

- [机场天气采集项目开发说明书.md](./机场天气采集项目开发说明书.md) — 完整项目规划（4 阶段 + 数据库设计）
- [deepseek.md](./deepseek.md) — 数据源补充（AWC API / NOAA ISD 对比）

---

## 📜 许可

（待定 — 根据用户选择添加）
