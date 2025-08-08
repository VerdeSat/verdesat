# VerdeSat Roadmap

The refactor completed in 2025 removed most hard-coded logic and unified
service layers. The following features are still open for development
and serve as a lightweight backlog.

## Remaining tasks

- **Caching layer** – avoid repeated Earth Engine downloads by caching
  intermediate composites and time series.
- **Cloud storage support** – implement `StorageAdapter` backends for
  S3 and GCS and allow CLI commands to output to cloud URIs.
- **Earth Engine auth management** – enable non-interactive
  authentication for automated deployments.
- **Interactive dashboard** – prototype a Streamlit or Dash app under
  `webapp/` for browsing results.
- **Advanced modeling** – add Prophet and LSTM forecasting with
  Optuna-based hyperparameter tuning.
- **Plugin architecture** – allow third-party ingestion backends (e.g.
  openEO or EODAG) via entry points.
- **Robust validation and error handling** – validate inputs and surface
  clear errors for missing data or failed requests.
- **Remove cosmetic hard-coded values** – font family in GIF
  annotations and example dates in CLI help text.
- **Expand unit tests and CI integration** – ensure new modules ship
  with tests and run in CI.
- MSA refresh path: support newer GLOBIO releases or regional MSA layers
- Repo inventory automation: generate MODULES.md from a script to keep docs in sync

# VerdeSat Roadmap — **From MVP to v1.0**

_Last updated: 2025-08-08_

## Milestones

### M0 — **MVP (today)**
- Streamlit demo (NDVI/MSAVI composites, KPI cards, NDVI decomposition)
- MetricEngine (intactness, shannon, fragmentation_norm) + B‑Score
- Landcover via Esri 10 m TS; artifacts saved to R2; presigned access

### M1 — **Foundations (Weeks 1–3)**
- Postgres+PostGIS (Neon/Supabase) + Alembic migrations
- FastAPI Core: Auth, Project, AOI CRUD
- Define R2 key convention & Artifact model
- Acceptance: create user → project → upload AOI; rows present in DB

### M2 — **Jobs & Artifacts (Weeks 4–6)**
- Queue (RQ/Redis or Cloudflare Queues)
- Worker container executes runs using MetricEngine; writes MetricSet JSONB
- Upload COGs/CSV/PDF to R2 under new prefixes; expose `/artifacts/{id}`
- Acceptance: `/aois/{id}/runs` creates job, finishes <10 min for 1 km² AOI

### M3 — **Unified Clients (Weeks 7–9)**
- CLI hits FastAPI (`login`, `aoi upload`, `run`, `get-metrics`)
- Streamlit reads from API, only uses presigned URLs for rasters
- Acceptance: both clients can show identical results for the same AOI/year

### M4 — **Hardening & Pilot (Weeks 10–12)**
- RBAC (user/project), basic rate‑limits, errors with codes
- Load test: 50 concurrent jobs; P95 < 12 min per job
- Pilot playbook (SLA, on-call, incident template)

### M5 — **Nice‑to‑Have / Stretch**
- Payments (Stripe) and usage metering
- Optional: GEDI canopy height & SAR biomass layers
- Optional: Hosted Titiler or dynamic tiles via Worker

---

## Backlog (rolling)
- Earth Engine non‑interactive auth for workers
- StorageAdapter: S3, R2 (done), GCS
- Advanced modeling: Prophet & LSTM (Optuna)
- Plugin backends (openEO/EODAG)
- Better PDF engine fallback & templating
- Monitoring: Loki + Grafana, Sentry

---

## Delivery principles
- Ship vertical slices that end in **user‑visible value** (API+CLI+UI).
- Keep costs near zero. Prefer serverless/managed where reasonable.
- Maintain clean separation: API (DB) vs Services (analytics) vs Clients.