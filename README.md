# Powerball RNG Engine

A data engineering, statistics, and software engineering portfolio platform that uses historical Powerball drawings as its dataset. It explores historical draw characteristics, probability, and combinatorics through a layered, testable architecture.

**This project does not predict lottery outcomes.** Powerball drawings are independent random events — past frequency has no bearing on future draws. Every analysis here is descriptive/statistical, not predictive.

## Features

- Weighted historical ticket generator
- Historical Powerball draw database
- Tennessee Powerball data updates
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
            -> Data Layer (data/)
```

```
lotto-app/
├── app.py                   # Streamlit UI — presentation only
├── fetch_tn_powerball.py    # CLI shim for the daily update GitHub Action
├── core/
│   ├── config.py            # centralized constants (ranges, thresholds, data path)
│   └── patterns.py          # shared ticket-pattern analysis (odd/even, low/high, sum, consecutive)
├── data/
│   └── repository.py        # numbers.json load/save
├── analytics_engine/
│   ├── frequency.py         # hot/cold/pair frequency
│   ├── scoring.py           # ticket scoring
│   ├── gaps.py               # number gap analysis
│   ├── condensation.py       # combinatorial condensation
│   └── charts.py             # Plotly chart builders
├── services/
│   ├── ticket_service.py     # ticket generation + validity filtering
│   └── update_service.py     # TN Powerball fetch/parse/update
└── tests/                    # pytest suite covering the layers above
```

Data currently lives in `lotto-app/numbers.json`. A future milestone migrates this to SQLite (then PostgreSQL) without changing the layers above it.

The repository root also contains a React/Vite/Tailwind scaffold. That is the **future production frontend** — it will consume a FastAPI layer built on top of the same application services once that milestone is reached. It is intentionally not wired up yet.

## Technologies

### Frontend (future production client)
- React
- Vite
- TailwindCSS

### Backend (current — research/analytics environment)
- Python
- Streamlit
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

### Running tests

```bash
cd lotto-app
pip install -r requirements-dev.txt
pytest
```

## Roadmap

- Historical data backfill + draw-date tracking (data engineering / ETL)
- SQLite, then PostgreSQL storage
- Statistical rigor layer (significance testing, confidence bands) on top of the analytics engine
- Expanded visualizations (heatmaps, trend-over-time)
- FastAPI layer exposing the application services
- React production frontend consuming the API
- CI running the test suite

## Author

Duley Williams
