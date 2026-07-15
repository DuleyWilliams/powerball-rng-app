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
- Plotly visual analytics, including frequency heatmaps, gap/sum/distribution charts, a recent-draw timeline, and a pair-frequency heatmap
- Statistical analysis engine (chi-square goodness-of-fit, confidence intervals, distribution tables)
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
├── cron_update.py             # IONOS cron updater — no Streamlit/Plotly/SciPy/Pandas, see below
├── run_cron_update.sh          # shell entry point for the IONOS Cron Job Manager
├── requirements-cron.txt       # minimal deps for cron_update.py only
├── database.db                # SQLite database (gitignored — regenerated, see below)
├── numbers.json               # Export/backup snapshot only, not read by the app
├── github_sync.secret.json.example  # committed placeholder — see "GitHub backup sync"
├── logs/                      # cron_update.py output (gitignored, created at runtime)
├── core/
│   ├── config.py             # centralized constants (ranges, thresholds, paths, source labels)
│   └── patterns.py           # shared ticket-pattern analysis (odd/even, low/high, sum, consecutive)
├── data/
│   ├── database.py           # SQLite schema + connection handling (the only SQL in the app)
│   ├── repository.py         # get_all_draws / get_latest_draw / get_recent_dated_draws / insert_draw / draw_exists / database_statistics
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
│   ├── statistics.py           # chi-square, confidence intervals, distribution analysis — see below
│   └── charts.py               # Plotly chart builders
├── services/
│   ├── ticket_service.py       # ticket generation + validity filtering
│   ├── update_service.py       # TN Powerball fetch/parse/update, routed through the ETL pipeline
│   └── github_sync_service.py  # pushes numbers.json to GitHub via the REST Contents API
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

## Statistics engine

`analytics_engine/statistics.py` replaces raw frequency counting with a proper statistical layer. **Everything in it is historical analysis only — Powerball drawings are independent random events, and nothing here predicts, forecasts, or improves the odds of a future draw.** The Streamlit dashboard's "Statistical Analysis" section repeats this warning directly above the numbers.

What it computes, all against the current draw history:

- **Frequency distributions** for every white ball (1-69) and every Powerball (1-26): observed count, expected count under a uniform draw, and a 95% confidence interval on the observed proportion (normal/Wald approximation).
- **Chi-square goodness-of-fit** for white balls and for Powerballs — tests whether the observed frequencies are consistent with uniform randomness, via `scipy.stats.chisquare`. Reports the statistic, degrees of freedom, p-value, and a plain-English interpretation at alpha=0.05.
- **White ball sum distribution** — mean, median, standard deviation, and a 95% confidence interval on the mean, plus a bucketed histogram (20-point buckets by default) spanning the theoretical min/max possible sum (15-335).
- **Odd/even and low/high distributions** — observed counts of each 0-5 split, compared against the *correct* expected counts computed via the hypergeometric distribution (`scipy.stats.hypergeom`), not a naive binomial(5, 0.5) assumption — white balls split 35 odd/34 even and 35 low/34 high out of 69, and draws are without replacement, so hypergeometric is the statistically correct model.
- **Frequency by number range/decade** — observed vs. expected counts bucketed into ranges of 10 (1-10, 11-20, ..., 61-69).

### Assumptions

- Confidence intervals use the normal approximation to the binomial (Wald interval), which is standard and adequate here given the large sample sizes involved (not the more conservative Wilson interval).
- Chi-square goodness-of-fit assumes expected cell counts are large enough for the chi-square approximation to hold (a common rule of thumb is >=5 per cell); with the current dataset (~1789 draws), expected counts per white ball (~130) and per Powerball (~69) are comfortably above that threshold.
- Odd/even and low/high expected distributions assume each drawing is 5 numbers drawn without replacement from a uniform 69-number pool — the correct null hypothesis for "the game is unbiased," which is exactly what these tests are checking, not assuming.

## Visualization dashboard

The Streamlit dashboard's "Visualization Dashboard" section turns the statistics/analytics engines into charts. **Like the rest of this app, every chart here summarizes historical data only — none of them predict or improve the odds of a future drawing.** The section repeats that warning above the charts.

All chart-building functions live in `analytics_engine/charts.py` — `app.py` only calls them and adds `st.subheader`/`st.caption` text; no calculation happens in the UI layer.

| Chart | What it shows | Built from |
|---|---|---|
| White ball / Powerball frequency heatmap | Each number shaded by historical draw count, laid out in a fixed grid (7 columns for white balls, 13 for Powerball) | `analytics_engine.statistics` frequency distributions |
| White ball / Powerball gap distribution | Drawings since each number last appeared, in number order (not sorted by gap, so the x-axis stays readable) | `analytics_engine.gaps` |
| White ball sum distribution (upgraded) | Histogram of the 5-white-ball sum per draw, now with a dashed mean line and a shaded 95% confidence band | `analytics_engine.statistics.white_ball_sum_statistics` — shown once, in the Statistical Analysis section, not duplicated here |
| Odd/even & Low/high distribution | Grouped bars comparing observed counts to the hypergeometric-expected counts | `analytics_engine.statistics` |
| Frequency by number range | Grouped bars, observed vs. expected, bucketed into ranges of 10 | `analytics_engine.statistics.frequency_by_range` |
| Recent draw timeline | White ball sum over time for the most recent 50 *dated* draws, colored by Powerball | `data.repository.get_recent_dated_draws` (new — see limitations) |
| White ball pair frequency heatmap | Full 69x69 matrix of how often each pair of white balls has appeared together | `analytics_engine.frequency.repeated_pairs` |

### Limitations

- **Recent draw timeline requires a known draw date.** The existing `Draw` shape (`[ball1..ball5, powerball]`) used everywhere else in the app has no date field, so `data/repository.py` gained one new read-only function, `get_recent_dated_draws()`, to fetch dated rows for this chart specifically. This is not a schema change — it reads the same `draws` table — and undated legacy/scraper rows are simply excluded from the timeline (a timeline of unknown-order points wouldn't mean anything).
- **The pair-frequency heatmap shows all 69x69 combinations.** A true network/node-link diagram was considered but would add real clutter and a heavier rendering cost for the same information; a heatmap reads cleanly at this size and every cell is still hoverable for the exact count.
- **Frequency heatmaps use a fixed grid layout**, not a literal Powerball ticket layout — the goal is readability (one row per visual chunk of numbers), not a physical reproduction.
- The sum distribution chart intentionally appears only once (Statistical Analysis section) rather than being duplicated in the Visualization Dashboard — Streamlit rejects two identical chart elements on the same page, and repeating identical content added no value.

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
- SciPy
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

## IONOS cron deployment

The Streamlit app isn't available on IONOS shared hosting, but the daily drawing update doesn't need it. `cron_update.py` is a standalone, dependency-light script that runs the exact same fetch → validate → insert-if-new → export pipeline as the Streamlit "Fetch Latest TN Powerball" button (both call `services.update_service.update_numbers()`), without importing Streamlit, Plotly, SciPy, Pandas, React, or `app.py`.

Confirmed target environment: Debian GNU/Linux, Python 3.9.2, pip 20.3.4, SQLite 3.34.1, IONOS Cron Job Manager.

### Deployment commands

```bash
# On the IONOS server, inside the cloned repo:
cd /kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app

# Optional but recommended: an isolated virtualenv so cron doesn't depend
# on whatever python3 happens to resolve to system-wide.
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-cron.txt

# Make sure the entry point is executable (git preserves this bit on
# commit, but set it explicitly after a fresh clone just in case):
chmod +x run_cron_update.sh cron_update.py

# One-time sanity check before wiring up cron:
./run_cron_update.sh --dry-run
echo "exit code: $?"        # expect 0
cat logs/cron_update.log    # expect one JSON line confirming the dry run
```

Add this exact command as the IONOS Cron Job Manager's job:

```
/kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app/run_cron_update.sh
```

`run_cron_update.sh` prefers `.venv/bin/python3` if that virtualenv exists next to it, and falls back to whatever `python3` is on `PATH` otherwise — so the venv step above is optional, not required.

### How it works

- **`cron_update.py`** resolves every path (`logs/`, `database.db`, `numbers.json`) from `Path(__file__).resolve().parent`, so it runs correctly regardless of cron's working directory.
- **Locking**: an exclusive, non-blocking `fcntl.flock()` on `logs/cron_update.lock` prevents two runs from overlapping if a previous invocation is still running when cron fires again. The lock is released automatically when the process exits, even on error.
- **Logging**: structured JSON lines (timestamp, level, message, and a stack trace field on errors) appended to `logs/cron_update.log` via Python's `logging` module. `run_cron_update.sh` also appends the raw stdout/stderr of the whole invocation to the same file, as a catch-all for failures that happen before Python's own logger is even configured (e.g. `python3` missing, a broken import).
- **Exit codes**: `0` for a successful insert *or* a no-new-drawing result (both are a healthy run), `1` for any fetch/validation/database failure, `2` if another run already holds the lock.
- **`--dry-run`**: verifies path resolution, locking, and logging without fetching or writing anything. Used for the deployment sanity check above and by the automated tests.

### Dependencies

`requirements-cron.txt` — deliberately just what `services.update_service` needs:

```
requests
beautifulsoup4
```

Everything else (SQLite access, the ETL pipeline, JSON export) is pure standard library. Streamlit/Plotly/SciPy/Pandas are never imported by this path, keeping the file count and install footprint small for IONOS's shared-hosting quota.

### Python 3.9 compatibility note

While building this, `services/update_service.py` was found to use `X | None` union-type syntax (PEP 604), which requires Python 3.10+ at runtime — it would have raised `TypeError` on import under Python 3.9.2. Since this module sits on the cron import path, it was changed to `typing.Optional[X]`, which is correct on every Python version this project targets. This is a pure type-annotation change with no behavior difference on any Python version — it does not affect the Streamlit app.

### Testing note

`tests/test_cron_update.py` covers a successful update, no-new-draw, fetch failure, lock contention, exit codes, and running from an unrelated working directory — all in-process or via a `--dry-run` subprocess, with no live network calls. Verified on a real Linux environment (the target IONOS host runs Debian; local development is Windows, so this suite was run and confirmed passing under WSL Ubuntu, including a genuine cross-process `fcntl.flock()` contention check with a second real process holding the lock).

### HTTP trigger (PHP)

IONOS's HTTP-GET-based cron system can't invoke a shell script directly, so `deployment/powerball_update.php` is a small, token-gated PHP endpoint that does nothing but authenticate the request and run `run_cron_update.sh` above by its absolute path, then report the result as JSON. It never touches the Python updater or Streamlit directly, and it does not weaken the existing `Require all denied` protection on `/powerball-cron` — that stays HTTP-unreachable; the PHP script invokes the shell script as a local OS process, not over HTTP.

Full deployment instructions, the exact cron URL, and security limitations are in the PHP file's own docblock and were provided in full when this endpoint was added — see `deployment/powerball_update.php` and `deployment/powerball_update.secret.php.example`.

### GitHub backup sync

After a successful database update, `cron_update.py` also pushes `lotto-app/numbers.json` to GitHub via `services/github_sync_service.py`, so the backup snapshot in the repo stays current even though it's generated on IONOS, not committed by a developer. This uses the GitHub REST **Contents API** directly over HTTPS (`requests`) — no `git`, git CLI, subprocess, SSH keys, or GitPython. It compares the remote file's decoded content against the local file first, and only creates a commit when they actually differ.

If the database update succeeds but the GitHub sync fails, `cron_update.py` exits with code `1` (a partial failure) and logs `github_sync_failed` with a safe, token-free message — the database itself is never left in a bad state, only the GitHub backup falls behind until the next successful run retries it.

#### Creating a fine-grained GitHub PAT

1. On GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. **Repository access**: select **Only select repositories** and choose only `DuleyWilliams/powerball-rng-app`. Do not grant access to any other repository.
3. **Permissions**: under **Repository permissions**, set **Contents** to **Read and write**. Leave every other permission at **No access**.
4. Set an expiration (GitHub recommends 90 days or less for fine-grained tokens) — see rotation procedure below.
5. Generate the token and copy it immediately (`github_pat_...`) — GitHub only shows it once.

#### Server secret-file setup

```bash
cd /kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app
cp github_sync.secret.json.example github_sync.secret.json
nano github_sync.secret.json   # paste the real token in place of the placeholder
chmod 600 github_sync.secret.json
```

Exact content template (`github_sync.secret.json`):

```json
{
  "token": "github_pat_REPLACE_WITH_A_REAL_FINE_GRAINED_TOKEN",
  "owner": "DuleyWilliams",
  "repo": "powerball-rng-app",
  "branch": "main"
}
```

This file is gitignored — it must never be committed. `github_sync.secret.json.example` (committed, no real token) documents the expected shape.

#### Token rotation procedure

1. Generate a new fine-grained token on GitHub (same steps as above).
2. On the server, edit `lotto-app/github_sync.secret.json` and replace the `token` value with the new one. No code changes or restarts needed — `cron_update.py` reads the file fresh on every run.
3. On GitHub, revoke the old token (**Settings → Developer settings → Personal access tokens → Fine-grained tokens** → find it → **Delete**).
4. Run the manual test command below to confirm the new token works before the next scheduled cron run.

#### Manual sync test command

```bash
cd /kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app
.venv/bin/python3 -c "
from services.github_sync_service import sync_numbers_json
result = sync_numbers_json()
print(result)
"
```

Expect `GithubSyncResult(changed=False, commit_sha=None)` if the repo is already current, or `GithubSyncResult(changed=True, commit_sha='...')` after a real push. A `GithubSyncError` means the token, permissions, or network need attention — its message is always safe to read/share, since it never includes the token.

## Roadmap

- PostgreSQL storage (production-grade successor to SQLite)
- FastAPI layer exposing the application services
- React production frontend consuming the API
- CI running the test suite

## Author

Duley Williams
