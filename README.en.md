<!-- LANG-SWITCH -->
[中文](./README.md) | **English**

# GSO — Global Surface Observatory

> Collect real-time aviation weather reports (METAR / TAF) from airports worldwide and store them in a local SQLite database — the foundation for downstream analytics, backtesting, alerts, and weather-prediction-market monitoring.

---

## ✨ Features

- **Primary path: AWC cache bundles**  
  A single HTTP fetch of `metars.cache.csv.gz` (updated every minute, ~234 KB) covers every reporting station globally — no per-ICAO API polling required. TAFs use `tafs.cache.xml.gz` (~300 KB).
- **Conditional GET 304 short-circuit**  
  Stores previous `ETag` / `Last-Modified` and sends `If-None-Match` / `If-Modified-Since` on each poll. When unchanged, returns in under a second with ~0 bandwidth.
- **Incremental writes**  
  At startup, loads `MAX(observation_time) per ICAO` as a cursor; only inserts rows whose `observation_time` is newer. `UNIQUE(icao, source_code, observation_time, raw_text)` is the final dedup safety net.
- **Raw + standardized fields side-by-side**  
  Every record stores `raw_text`, standardized columns (temperature, dewpoint, wind, visibility, altimeter, flight_category), and the full `raw_json` — everything can be recomputed or cross-validated later.
- **API fallback path**  
  AWC / AVWX JSON API clients are available for precise per-ICAO queries — useful for backfilling gaps or focused analysis.
- **City-based nearby airports lookup**  
  `gso city <city>` accepts any-language city name (Chinese / English / Japanese / etc.), geocodes it, finds the N nearest airports, and aggregates the last 24h temperature extremes.
- **SPECI detection**  
  `metar_reports.metar_type` distinguishes routine METARs from SPECI (special observations).
- **Single-file exe distribution**  
  Unified CLI with subcommands, packaged via PyInstaller (~25 MB) — no Python needed on the target machine.

---

## 🚀 Quick Start

### Option 1: Prebuilt exe (Windows, recommended)

```cmd
:: 1. Copy the dist/gso/ folder (contains gso.exe and _internal/) to any location, e.g. C:\GSO\
cd C:\GSO

:: 2. Initialize the database (creates db\aviation_weather.db in cwd)
gso.exe init

:: 3. First poll (pulls the full ~4800 METAR + 2700 TAF snapshot)
gso.exe poll

:: 4. Query the latest reports
gso.exe show RJTT ZBAA KJFK EGLL
```

### Option 2: Run from source

```bash
# 1. Clone and enter
git clone https://github.com/hunkguo/global_surface_observatory.git
cd global_surface_observatory

# 2. Create venv and install deps
python -m venv venv
venv\Scripts\activate              # Windows
# source venv/bin/activate         # Linux/macOS
pip install -r requirements.txt

# 3. Initialize and run
python gso.py init
python gso.py poll
python gso.py show RJTT ZBAA
```

---

## 📖 Commands

```
gso <command> [options]

  init            Create or migrate the SQLite database
  fetch-airports  Download global airport codes from OurAirports (~60k rows)
  poll            Pull AWC cache and write incrementally (primary path)
  fetch           Precise per-ICAO query via JSON API (fallback)
  show            Print latest METAR/TAF for one or more ICAOs
  city            City name -> nearby airports -> last N hours temperature
```

Use `gso <command> --help` to see per-command options.

### `gso init`

Idempotent: creates the DB if missing, or applies column migrations (e.g. adding `metar_type`, `sea_level_pressure_mb` to older databases).

### `gso poll`

Each run:
1. Conditional GET on `metars.cache.csv.gz` and `tafs.cache.xml.gz`.
2. 304 → log a `not_modified` run and exit.  
   200 → parse, filter with cursor, batch `INSERT OR IGNORE`.
3. Update `http_cache_state` (ETag / Last-Modified) and `fetch_runs` (insert count).

Options:

| Flag | Description |
| --- | --- |
| `--db PATH` | SQLite file path, default `./db/aviation_weather.db` |
| `--loop N` | In-process loop every N seconds (dev/debug — use external scheduler in production) |
| `--skip-metar` | Skip METAR this round |
| `--skip-taf` | Skip TAF this round |
| `--quiet` | Suppress log output |

### `gso fetch`

Precise per-ICAO query via JSON API (fallback path).

```bash
gso fetch --icaos RJTT,ZBAA,KJFK --sources awc
gso fetch --country CN --limit 20 --sources awc,avwx
```

AVWX requires the `AVWX_API_KEY` environment variable (free signup at [avwx.rest](https://avwx.rest/)).

### `gso show`

Print the latest METAR + TAF for one or more ICAOs:

```bash
gso show RJTT                      # single airport
gso show RJTT ZBAA KJFK EGLL LFPG  # multiple
```

### `gso fetch-airports`

Pull the OurAirports public CSV, load into the `airports` table, and emit `shared_data/airports.json`.

```bash
gso fetch-airports                    # all airports (~60k)
gso fetch-airports --country CN       # China only
gso fetch-airports --limit 100        # debug
```

### `gso city`

Accept a city name in any language (Chinese / English / Japanese / etc.), geocode it, find the nearest N airports within the radius, and summarize the last N hours of temperature.

```bash
gso city Beijing                              # single city, defaults: 100km / 24h / top 3
gso city Beijing Shanghai Tokyo London        # multiple cities
gso city Shanghai --radius 50 --top 2         # 50km radius, 2 airports
gso city Beijing --hours 6                    # last 6h window
```

**Prerequisite**: run `gso fetch-airports` first to populate the global airports table. Geocoding uses OpenStreetMap Nominatim (no API key, but rate-limited to 1 req/s).

**Sample output**:

```
=== Tokyo ===
  Location : Tokyo, Japan
  Coords   : (35.6769, 139.7639)
  Window   : 2026-04-18T04:18:25Z  ->  2026-04-19T04:18:25Z  (last 24h, UTC)

  ICAO   Name                                 Dist    Tmax (°C / °F)    Tmin (°C / °F)     N  Latest
  --------------------------------------------------------------------------------------------------
  RJTI   Tokyo Heliport                       8.2km   23.0°C /  73.4°F   23.0°C /  73.4°F     1  2026-04-19 03:00
  RJTT   Tokyo Haneda International Airpo    14.3km   21.0°C /  69.8°F   21.0°C /  69.8°F     1  2026-04-19 03:00
  RJTF   Chofu Airport                       21.3km   25.0°C /  77.0°F   25.0°C /  77.0°F     1  2026-04-19 03:00
```

> ⚠️ `N` is the number of reports inside the window — on day one this is small; after running `poll` for a while, `Tmax` / `Tmin` reflect the real intra-day extremes. `--` means the airport has no METAR in the AWC cache (typical for heliports / military / restricted airports).

---

## ⏰ Scheduling

### Windows Task Scheduler (recommended)

1. `Win + R` → `taskschd.msc`
2. Create task → trigger: **On a schedule**, every 1 minute
3. Action:
   - Program: `C:\GSO\gso.exe` (or `python.exe`)
   - Arguments: `poll --quiet` (Python mode: `gso.py poll --quiet`)
   - Start in: `C:\GSO` (important — this decides where data files live)

### Linux / macOS cron

```crontab
* * * * * cd /opt/gso && /opt/gso/gso poll --quiet >> /var/log/gso.log 2>&1
```

### Dev / debug

Use the in-process loop directly:

```bash
gso poll --loop 60
```

---

## 🗄️ Database Schema

File: `db/aviation_weather.db` (SQLite 3)

| Table | Purpose |
| --- | --- |
| `airports` | Global airport master data (ICAO / IATA / city / country / lat / lon / elevation) |
| `weather_sources` | Data source registry (`awc` / `avwx`) |
| `fetch_runs` | Per-poll audit log (started/finished/status/insert count) |
| `metar_reports` | METAR + SPECI raw and standardized fields |
| `taf_reports` | TAF raw and top-level fields |
| `forecast_segments` | TAF forecast segments (reserved; not populated in MVP) |
| `http_cache_state` | HTTP conditional-GET state (url / etag / last_modified) |

Core columns (`metar_reports`):

```
icao, source_code, observation_time, raw_text, metar_type (METAR/SPECI),
temperature_c, dewpoint_c, wind_dir, wind_speed, gust, visibility,
altimeter (hPa), sea_level_pressure_mb, flight_category (VFR/MVFR/IFR/LIFR),
raw_json (full CSV/API source fields)

UNIQUE(icao, source_code, observation_time, raw_text)
```

> ⚠️ **Unit normalization**: `altimeter` is always stored in hPa. The CSV source provides inHg; the client multiplies by `33.86389` automatically.

### Useful queries

```sql
-- Latest METARs for a given ICAO in the last hour
SELECT observation_time, metar_type, temperature_c, wind_dir, wind_speed,
       visibility, flight_category, raw_text
FROM metar_reports
WHERE icao = 'RJTT'
  AND observation_time > datetime('now', '-1 hour')
ORDER BY observation_time DESC;

-- Stations currently in LIFR
SELECT icao, observation_time, visibility, raw_text
FROM metar_reports
WHERE flight_category = 'LIFR'
  AND observation_time > datetime('now', '-30 minutes');

-- Coverage by source
SELECT source_code, COUNT(DISTINCT icao) AS stations, COUNT(*) AS reports
FROM metar_reports GROUP BY source_code;
```

---

## 🌐 Data Sources

| Source | Type | Role | Frequency / Limits |
| --- | --- | --- | --- |
| [AWC `metars.cache.csv.gz`](https://aviationweather.gov/data/cache/metars.cache.csv.gz) | Batch CSV | METAR primary | Updated every minute |
| [AWC `tafs.cache.xml.gz`](https://aviationweather.gov/data/cache/tafs.cache.xml.gz) | Batch XML | TAF primary | Updated every minute |
| [AWC API](https://aviationweather.gov/api/data/metar) | JSON API | Per-ICAO fallback | 100 req/min, 400 rows/req |
| [AVWX API](https://avwx.rest/) | JSON API | Aggregator fallback | API key required |
| [OurAirports](https://ourairports.com/data/) | CSV | Airport master data | Public domain |

> For non-airport ground stations, consider adding [NOAA ISD-lite](https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/) (35,000+ stations worldwide; details in `deepseek.md`).

---

## 🏗️ Building the exe from source

```bash
# 1. Install build deps
pip install -r requirements-dev.txt

# 2. Build with the included spec file
pyinstaller gso.spec

# Output: dist/gso/gso.exe + dist/gso/_internal/
```

Or rebuild the spec from scratch:

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

`--onefile` yields a smaller, more portable exe — but it re-extracts to a temp dir on every invocation, which is not ideal for per-minute polling.

---

## 📁 Project Structure

```
global_surface_observatory/
├── gso.py                            # unified CLI entrypoint
├── gso.spec                          # PyInstaller build config
├── requirements.txt                  # runtime deps
├── requirements-dev.txt              # build deps (pyinstaller)
│
├── data_sources/
│   ├── awc_cache_client.py           # primary: CSV/XML + conditional GET
│   ├── awc_client.py                 # fallback: AWC JSON API
│   ├── avwx_client.py                # fallback: AVWX JSON API
│   ├── airport_codes_client.py       # OurAirports CSV
│   └── geocode_client.py             # Nominatim geocoding (used by gso city)
│
├── parsers/
│   ├── metar_parser.py               # METAR parsing (API mode)
│   └── taf_parser.py                 # TAF parsing (API mode)
│
├── scripts/
│   ├── init_aviation_db.py           # gso init
│   ├── fetch_airport_codes.py        # gso fetch-airports
│   ├── poll_aviation_weather.py      # gso poll (primary)
│   ├── fetch_aviation_weather.py     # gso fetch (API fallback)
│   ├── show_latest.py                # gso show
│   └── weather_by_city.py            # gso city
│
├── storage/
│   ├── sqlite_schema.sql             # all-table DDL
│   └── sqlite_repo.py                # connection / cursor / writes
│
├── db/                               # runtime-generated, git-ignored
├── shared_data/                      # runtime-generated, git-ignored
├── 机场天气采集项目开发说明书.md     # original project spec
└── deepseek.md                       # supplementary notes (NOAA ISD, etc.)
```

---

## ⚠️ Known Limitations

1. **Same-minute corrections**  
   The cursor uses strict `>`, so a CC/AMD correction arriving within the same `observation_time` is skipped. Switch to `>=` and rely on UNIQUE dedup if corrections matter — at the cost of attempting to insert every row on every poll.
2. **AWC cache covers ~4,800 METARs**  
   The cache bundle includes "official exchange" stations, not every airport globally. For missing stations, use the API mode or plug in NOAA ISD.
3. **API historical range is 15 days**  
   For longer history, archive from Iowa Environmental Mesonet or NOAA ISD.
4. **ICAO ≠ city**  
   Multi-airport cities mean airport temperature ≠ city temperature. When used for weather-prediction-market monitoring, always align with the market's official settlement station.
5. **altimeter vs sea_level_pressure_mb**  
   `altimeter` is QNH (hPa); `sea_level_pressure_mb` is sea-level pressure (sometimes provided by the CSV source). They are close but not identical.

---

## 📚 Reference Documents

- [机场天气采集项目开发说明书.md](./机场天气采集项目开发说明书.md) — full project plan (4 phases + DB design)
- [deepseek.md](./deepseek.md) — data-source notes (AWC API / NOAA ISD comparison)

---

## 📜 License

(TBD — pending user choice)
