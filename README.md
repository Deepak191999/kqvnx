# Wind Procurement Desk

A decision-support web application for the day-ahead power procurement team at a UK
energy utility.

The desk must buy thermal power on the day-ahead market **before 11:00 on D-1** to cover
whatever national wind generation will not supply on delivery day D. That decision rests
entirely on a forecast. This application does two things:

1. **Shows the forecast they are actually allowed to act on** — the newest Elexon WINDFOR
   vintage published at or before the auction gate closure, never a later revision.
2. **Quantifies how wrong that forecast tends to be**, so the buyer can size a hedge
   against it rather than treating the forecast as truth.

Data is national-level GB wind from Elexon BMRS only, scoped to purchase decisions taken
in **January 2026** (delivery days 2 Jan – 1 Feb 2026).

---

## Headline findings

Computed from 744 delivery hours across 31 delivery days, always at the gate-closure
vintage.

| Metric | Value |
|---|---|
| Mean absolute error (MAE) | **2,013 MW** (17.8% of mean outturn) |
| RMSE | 2,506 MW (22.2%) |
| Mean bias | **+1,730 MW** |
| Hours where the forecast exceeded outturn | **84.3%** |
| P10 – P90 error range | −489 MW to +4,144 MW |

**The error is one-sided, not random.** WINDFOR overstated metered wind in roughly five
hours out of six, and 86% of the average absolute error is systematic bias rather than
noise. A desk that hedges only the spread is structurally short on almost every delivery
day.

The most plausible explanation is scope and curtailment: WINDFOR projects what the wind
fleet *could* generate, while FUELHH meters what it was actually allowed to deliver after
Balancing Mechanism bid-offs and network constraints. Consistent with that reading, the
bias is largest in the top outturn quintiles, which is when constraint curtailment binds.

### Correcting the bias is worth about 40% of the error

A single multiplicative factor, refitted each day on only the delivery days that had
already settled, was tested walk-forward over 24 days (576 hours):

| | MAE | RMSE | Bias |
|---|---|---|---|
| Forecast as published | 2,063 MW | 2,588 MW | +1,808 MW |
| Bias-calibrated | **1,230 MW** | **1,647 MW** | +212 MW |
| Improvement | **−40.4%** | **−36.4%** | — |

No day contributes to its own correction, so these are genuine out-of-sample results. The
fitted factor is stable across the month (0.86–0.90), which is what makes it usable rather
than a curve-fitting artefact.

### Lead time costs accuracy

Error grows monotonically with how far ahead the forecast looks:

| Lead time | 0–6h | 6–12h | 12–18h | 18–24h | 24–30h | 30–36h | 36–48h | 48–72h |
|---|---|---|---|---|---|---|---|---|
| nMAE | 14.8% | 15.3% | 16.2% | 17.4% | 17.5% | 18.3% | 20.0% | 20.3% |

The day-ahead gate closure forces the desk to commit at a **14.5–37.5 hour** lead time —
well before the forecast reaches its best skill. That gap is a structural cost of the
market's timetable, not a failure of the forecaster, and it is the reason the error has to
be priced rather than eliminated.

---

## Running it

### Docker (recommended)

```bash
docker compose up --build
```

- Application: <http://localhost:8080>
- API docs (OpenAPI): <http://localhost:8000/docs>

The frontend is served by nginx, which proxies `/api` to the backend container, so the
browser stays same-origin and no CORS configuration is needed.

> Note: the Docker images are defined but were not built during development, as Docker was
> not available on the authoring machine. The equivalent local workflow below was used
> throughout and is fully verified.

### Local development

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20):

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to port 8000.

### Tests

```bash
cd backend && python -m pytest
```

46 tests, covering vintage selection, metric arithmetic, the forecast/outturn alignment
rules, calibration leakage, and the HTTP contract.

### Refreshing the data

The repository ships with a pre-built SQLite snapshot (`backend/data/wind.db`) so the app
runs offline. To rebuild it from Elexon:

```bash
cd backend && python -m app.services.ingest
```

---

## Deployment

| | URL |
|---|---|
| **Application** | <https://kqvnx.vercel.app> |
| **API** | <https://kqvnx-api.vercel.app> |
| API docs (OpenAPI) | <https://kqvnx-api.vercel.app/docs> |

Both halves run on Vercel as two projects, each with an unambiguous root directory.

- **`kqvnx`** — root `frontend/`, the static Vite build. `VITE_API_BASE_URL` is baked in at
  build time.
- **`kqvnx-api`** — repo root, the FastAPI app as a Python serverless function at
  `api/index.py`, which puts `backend/` on the import path and exports the same app.

Two things are worth knowing if you redeploy:

- **No `rewrites`.** Vercel routes every unmatched path to the function already, preserving
  the original path. Adding a rewrite to `/api/index` makes the function receive the literal
  path `/api/index`, and every route 404s.
- **The bundle is read-only.** `api/index.py` sets `READ_ONLY_DB=1`, which opens the SQLite
  snapshot in read-only URI mode instead of trying to create a journal beside it.

The root `requirements.txt` is deliberately narrower than `backend/requirements.txt` —
uvicorn and httpx are not needed in the function — to stay inside the bundle size limit.

Fallbacks, if the Python function is not viable on another plan:

| Component | Platform | Config |
|---|---|---|
| Backend | Render | `docs/render.yaml` (Docker, free tier) — copy to the repo root to use |
| Backend | Heroku | `backend/heroku.yml` container build, or `Procfile` |

> `render.yaml` is kept under `docs/` rather than the repo root because the Vercel CLI
> parses a root-level one as a multi-service monorepo manifest and refuses to deploy.

The API permits any `*.vercel.app` origin by regex plus whatever is listed in
`ALLOWED_ORIGINS`, so preview deployments and a split deployment both work without
reconfiguration.


---

## How it is put together

```
.
├── vercel.json                 Vercel config for the API serverless function
├── requirements.txt            Trimmed dependency set for the function only
├── docs/render.yaml            Fallback API host (Docker, free tier)
├── docker-compose.yml          API + nginx-served frontend
├── .github/workflows/ci.yml    Backend tests, frontend typecheck and build
├── api/
│   └── index.py                Vercel serverless entrypoint for the FastAPI app
├── backend/
│   ├── Dockerfile              Python 3.12 slim, non-root, snapshot baked in
│   ├── Procfile, runtime.txt   Heroku deployment
│   ├── pyproject.toml          pytest + ruff configuration
│   ├── requirements.txt        Pinned runtime dependencies
│   ├── data/wind.db            Pre-ingested January 2026 snapshot (committed)
│   ├── app/
│   │   ├── main.py             FastAPI app, CORS, lifespan, /health
│   │   ├── core/
│   │   │   ├── config.py       Domain constants: gate closure, date scope, paths
│   │   │   └── db.py           SQLite schema and connection handling
│   │   ├── services/
│   │   │   ├── elexon_client.py  HTTP client for the two BMRS stream endpoints
│   │   │   ├── ingest.py         One-shot fetch → normalise → store
│   │   │   ├── vintage.py        Gate closure and as-of forecast selection
│   │   │   ├── analysis.py       Forecast/outturn pairing and error statistics
│   │   │   ├── calibration.py    Walk-forward bias correction
│   │   │   └── cache.py          Process-level memoisation of derived frames
│   │   └── routers/
│   │       ├── decision.py     /api/meta, /api/decision/{date}, /api/vintages/{date}
│   │       └── accuracy.py     /api/accuracy/*
│   └── tests/                  conftest fixtures + four test modules
└── frontend/
    ├── Dockerfile, nginx.conf  Build with Node, serve static via nginx
    ├── vercel.json             SPA rewrites and asset caching
    └── src/
        ├── App.tsx             Shell, tab routing, theme toggle
        ├── pages/
        │   ├── DecisionView.tsx   The buyer's working screen
        │   └── AccuracyView.tsx   Quantified error and calibration evidence
        ├── components/         Card, Tile, Legend, shared chart tooltip
        ├── lib/                Typed API client, formatters, fetch hook
        └── styles/             Design tokens and layout
```

### API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness and snapshot presence |
| `GET /api/meta` | Date scope, conventions, row counts, source descriptions |
| `GET /api/decision/{date}` | Gate-closure forecast curve, P10–P90 band, calibration, provenance |
| `GET /api/vintages/{date}` | Every vintage for a day, flagged either side of the cut-off |
| `GET /api/accuracy/summary` | Headline metrics, risk read, calibration comparison |
| `GET /api/accuracy/by-day` | Per-delivery-day statistics |
| `GET /api/accuracy/by-hour` | Time-of-day error profile |
| `GET /api/accuracy/by-horizon` | Error against lead time, across all vintages |
| `GET /api/accuracy/distribution` | Error histogram |
| `GET /api/accuracy/series` | Full paired time series |

---

## Design decisions worth knowing

**Vintage discipline is enforced in one place.** `services/vintage.py` is the only code
that decides which forecast a delivery day is entitled to see. Everything downstream —
the decision view, every accuracy metric, the calibration fit — consumes its output, so
there is a single place to audit for hindsight. The rule is expressed as "11:00 Europe/London
on D-1" rather than a hardcoded UTC hour, and there is a test proving it shifts correctly
under BST even though the January scope never crosses the boundary.

**Alignment reconciles down, never up.** WINDFOR is hourly; FUELHH is half-hourly. The two
metered settlement periods inside an hour are averaged onto the forecast's hourly grid.
Interpolating the forecast up to half-hourly would have produced values Elexon never
published, and would have doubled the apparent sample size without adding information.
Hours with only one metered period are dropped rather than half-counted.

**Error carries a sign, and the sign has a trading meaning.** Throughout,
`error = forecast − actual`. Positive means wind under-delivered and the desk was short at
delivery. Collapsing to absolute error everywhere would have hidden the single most
important finding in this dataset.

**The uncertainty band is empirical.** P10/P90 come from the observed distribution of
gate-closure errors at the same hour of day — no normality assumption. With one month of
data a parametric interval would imply precision the sample cannot support.

**Calibration refuses to fit on thin history.** Below seven settled days the service
returns no correction at all and the product falls back to the raw forecast, rather than
shipping a factor fitted on noise.

**The database is a committed snapshot.** A live Elexon dependency would make the deployed
demo fail whenever the upstream API was slow or down, and would make the numbers in this
README unreproducible. Ingest is a separate one-shot job.

### Known limitations

- One month of data. The calibration factor is stable within January 2026 but seasonal
  behaviour is unverified; it should be refitted on a rolling window in production.
- The curtailment explanation for the bias is inference from the error's shape, not
  measurement. Confirming it needs Balancing Mechanism bid-offer acceptance data, which is
  outside the scope set for this exercise.
- Gate closure is modelled as a single 11:00 cut-off. A desk also trading intraday would
  need multiple decision points.
- No authentication. The application serves public market data and holds no user state.

---

## AI tool usage

This application was built with assistance from **Claude (Anthropic)**, used throughout
for code generation, exploratory data analysis, and documentation drafting. The domain
framing, the vintage-correctness requirement, the choice of metrics, and the validation
approach for the calibration were directed by me; all analytical findings were verified
against the data before being included here.

## Data sources

- [Elexon BMRS FUELHH](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)
  — half-hourly metered generation by fuel type, filtered to `fuelType=WIND`.
- [Elexon BMRS WINDFOR](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
  — hourly national wind generation forecast, republished roughly five times a day.
