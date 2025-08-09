# VerdeSat Roadmap

The refactor completed in 2025 removed most hard-coded logic and unified
service layers. The following features are still open for development
and serve as a lightweight backlog.

## Remaining tasks

- **Caching layer** – avoid repeated Earth Engine downloads by caching
  intermediate composites and time series.
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

# VerdeSat Roadmap — From MVP to v1.0

_Last updated: 2025-08-08_

## Milestones & Acceptance

### M0 — MVP (today)
- Streamlit demo (NDVI/MSAVI composites, KPI cards, NDVI decomposition)
- MetricEngine (intactness, shannon, fragmentation_norm) + B‑Score
- Landcover via Esri 10 m TS; artifacts saved to R2; presigned access
- R2 helper in webapp (private bucket → signed URLs); Folium+Titiler tiles

**Acceptance:** App at `app.verdesat.com` shows demo project in <10 s; CSV/PDF export works.

---

### M1 — Foundations (Weeks 1–3)
- Postgres+PostGIS (Neon/Supabase) + Alembic migrations
- FastAPI Core: Auth, Project, AOI CRUD
- Define R2 key convention & Artifact model; include MSA artifact naming

**Acceptance:** Create user → project → upload AOI via API; rows visible in DB.

---

### M2 — Jobs & Artifacts (Weeks 4–6)
- Queue (RQ/Redis or Cloudflare Queues) + Worker container
- Worker executes runs using MetricEngine/Landcover/TimeSeries/MSA; writes MetricSet JSONB
- Upload COG/CSV/PDF artifacts to R2; endpoint `/artifacts/{id}` presigns URLs

**Acceptance:** `POST /aois/{id}/runs` completes <10 min for 1 km² AOI; artifacts downloadable.

---

### M3 — Unified Clients (Weeks 7–9)
- CLI hits FastAPI (`login`, `aoi upload`, `run`, `get-metrics`)
- Streamlit reads metrics via API; charts fetched as PNGs (API renders)

**Acceptance:** CLI and Web show identical metrics for the same AOI/year.

---

### M4 — Hardening & Pilot (Weeks 10–12)
- RBAC (user→project), basic rate‑limits; error codes and retry taxonomy
- Load test: 50 concurrent jobs (P95 < 12 min per 1 km² AOI)
- Pilot playbook: SLA, on‑call, incident template

**Acceptance:** Pilot customers onboarded; dashboards stable under load.

---

### M5 — Stretch / Nice‑to‑Have
- Payments (Stripe) & usage metering
- Optional layers: GEDI canopy height, SAR biomass
- Optional: managed Titiler / Worker‑based tiling

---

## Backlog (rolling)
- Earth Engine non‑interactive auth for workers
- StorageAdapter: S3, R2 (done), GCS
- Advanced modeling: Prophet & LSTM (Optuna)
- Plugin backends (openEO/EODAG)
- Better PDF templating & fallbacks
- Monitoring: Loki + Grafana, Sentry
- MSA refresh path for newer GLOBIO releases or regional layers
- Repo inventory automation: regenerate `docs/MODULES.md` from `scripts/inventory.py`

---

## Delivery principles
- Ship vertical slices that end in **user‑visible value** (API+CLI+UI).
- Keep costs near zero; prefer managed/serverless.
- Maintain clear separation: **API (DB)** vs **Services (analytics)** vs **Clients (CLI/Web)**.