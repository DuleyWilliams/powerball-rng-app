# Powerball RNG Engine

A data engineering, statistics, and software engineering portfolio platform that uses historical Powerball drawings as its dataset. It explores historical draw characteristics, probability, and combinatorics through a layered, testable architecture.

**This project does not predict lottery outcomes.** Powerball drawings are independent random events — past frequency has no bearing on future draws. Every analysis here is descriptive/statistical, not predictive.

## Features

- Weighted historical ticket generator
- SQLite-backed historical Powerball draw database
- ETL pipeline with validation, logging, and a historical bulk importer
- Tennessee Powerball daily data updates
- Hot / cold number analysis
- Powerball frequency tracking
- Repeated pair analysis
- Number gap analysis
- Ticket scoring engine
- Combinatorial condensation
- Plotly visual analytics
- CSV export

## Architecture

The Streamlit app (`lotto-app/`) is the research/experimentation environment. It is organized in layers so business logic stays reusable by a future API/React client rather than tied to Streamlit UI code:

```
UI (app.py)
  -> Application Services (services/)
       -> Analytics Engine (analytics_engine/)
            -> Data Layer (data/) <- ETL Pipeline (etl/)
```

```
lotto-app/
├── app.py                    # Streamlit UI — presentation only
├── fetch_tn_powerball.py     # CLI shim for the daily update GitHub Action
├── import_history.py         # CLI: bulk historical import (NY Open Data -> SQLite)
├── database.db                # SQLite database (gitignored — regenerated, see below)
├── numbers.json               # Export/backup snapshot only, not read by the app
├── core/
│   ├── config.py             # centralized constants (ranges, thresholds, paths, source labels)
│   └── patterns.py           # shared ticket-pattern analysis (odd/even, low/high, sum, consecutive)
├── data/
│   ├── database.py           # SQLite schema + connection handling (the only SQL in the app)
│   ├── repository.py         # get_all_draws / get_latest_draw / insert_draw / draw_exists / database_statistics
│   ├── migration.py          # idempotent numbers.json -> SQLite migration
│   └── json_export.py        # SQLite -> numbers.json backup export
├── etl/
│   ├── extract.py            # pulls raw records from numbers.json or NY Open Data — no interpretation
│   ├── transform.py          # reshapes raw records into a canonical TransformedDraw — never rejects
│   ├── validate.py           # pure business-rule validation (ranges, duplicates, dates) — never persists
│   └── load.py                # dedupes against the repository and persists; the only ETL module touching SQLite
├── analytics_engine/
│   ├── frequency.py          # hot/cold/pair frequency
│   ├── scoring.py             # ticket scoring
│   ├── gaps.py                 # number gap analysis
│   ├── condensation.py         # combinatorial condensation
│   └── charts.py               # Plotly chart builders
├── services/
│   ├── ticket_service.py       # ticket generation + validity filtering
│   └── update_service.py       # TN Powerball fetch/parse/update, routed through the ETL pipeline
└── tests/                      # pytest suite covering every layer above
```

The repository root also contains a React/Vite/Tailwind scaffold. That is the **future production frontend** — it will consume a FastAPI layer built on top of the same application services once that milestone is reached. It is intentionally not wired up yet.

## Data platform

### SQLite is now the primary data source

`database.db` holds a single `draws` table:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | autoincrement |
| `draw_date` | DATE | nullable — see "undated legacy rows" below |
| `ball1`..`ball5` | INTEGER | sorted ascending white balls |
| `powerball` | INTEGER | |
| `source` | TEXT | `legacy_json`, `data.ny.gov`, or `powerball.com` — provenance of every row |
| `created_at` | TIMESTAMP | row insert time, defaults to `CURRENT_TIMESTAMP` |

Indexed on `draw_date`, `ball1`..`ball5`, and `powerball`.

`database.db` is **gitignored** — it's a derived artifact, rebuilt automatically:
- On every app startup, `data.migration.migrate_json_to_sqlite()` runs (idempotent — safe every time) to (re)create the schema and pull in anything from `numbers.json` not already present.
- `python import_history.py` (see below) populates it with full official history.

`numbers.json` is kept only as an **export/backup** snapshot — it's written to after every successful live update, but the running app never reads it back in.

### Undated legacy rows

The original `numbers.json` had no draw-date field, so its 6 entries are migrated with `draw_date = NULL` (`source = "legacy_json"`). Because a real draw date is the natural unique key for deduplication, undated rows use a fallback: an exact match on all 6 numbers, checked in both directions, so a legacy row and its later-dated equivalent (from the historical importer or a fresh scrape) are recognized as the same draw regardless of which one was inserted first.

### ETL pipeline

Four single-responsibility modules under `etl/`, all reused by both the historical importer and the numbers.json migration:

```
extract.py   -> transform.py    -> validate.py         -> load.py
(raw source)    (parse/reshape,     (business rules,       (dedupe via repository,
                 never rejects)      never touches DB)       then persist)
```

Validation rejects: missing numbers, invalid white-ball/powerball ranges, duplicate white balls within a ticket, unparseable dates, missing dates (when required), and future dates. Duplicate **rows** (an already-persisted draw) are caught at the load stage via the repository, since that requires a database lookup. Every rejection and every skipped duplicate is logged via the standard `logging` module.

### Historical importer

```bash
cd lotto-app
python import_history.py
```

Pulls the full Powerball drawing history from the [NY State Open Data Socrata dataset](https://data.ny.gov/resource/d6yy-54nr.json) (official public archive, 2010-present) and loads it through the ETL pipeline above, printing progress and a final summary (imported / skipped / failed / newest draw / oldest draw / total rows).

**Drawings before the October 2015 format change are intentionally rejected.** Powerball changed from a 5/59 + 1/35 game to the current 5/69 + 1/26 format in October 2015; older draws fail the current white-ball/powerball range validation and are counted under "Failed" with a logged reason. This isn't a bug — it's a deliberate scope boundary, since this app models one specific game format. Multi-era format support is a candidate for a future milestone, not this one.

As of the last run: **1789 rows** imported (2010-02-03 through the present), with pre-2015 draws correctly rejected by range validation.

## Technologies

### Frontend (future production client)
- React
- Vite
- TailwindCSS

### Backend (current — research/analytics environment)
- Python
- Streamlit
- SQLite
- Pandas
- Plotly
- Requests
- BeautifulSoup
- pytest

## Running the app

```bash
cd lotto-app
pip install -r requirements.txt
streamlit run app.py
```

SQLite migration runs automatically on startup. To load full official history first:

```bash
python import_history.py
```

### Running tests

```bash
cd lotto-app
pip install -r requirements-dev.txt
pytest
```

## Roadmap

- PostgreSQL storage (production-grade successor to SQLite)
- Statistical rigor layer (significance testing, confidence bands) on top of the analytics engine
- Expanded visualizations (heatmaps, trend-over-time)
- FastAPI layer exposing the application services
- React production frontend consuming the API
- CI running the test suite

## Author

Duley Williams
