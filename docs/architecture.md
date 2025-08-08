# VerdeSat Architecture — Current State, Target v1.0, Migration Plan

_Last updated: 2025-08-08_

---

## 0) TL;DR
- **Today (MVP):** Python monorepo; EO analytics in pure Python; Streamlit dashboard; private COGs/CSV/PDFs on **Cloudflare R2** accessed via **presigned URLs**; Folium/Leaflet tiles served via Titiler; CLI and webapp reuse the same service classes.
- **Target v1.0:** One **FastAPI Core** (Auth, Projects, AOIs, Jobs, MetricSets, Artifacts) + **Postgres/PostGIS** (metadata & metrics) + **Workers/Queue** (long jobs) + **R2** (heavy artifacts). Streamlit & CLI become thin clients of this API.
- **Why:** Single source of truth, multi-tenant, cloud‑native, cheap to run, easy to extend.

---

## 1) Current State (MVP)

### 1.1 Repository & Modules (high‑level)
```
verdesat/
├─ analytics/
│  ├─ ee_chipping.py         # chip export helpers (GEE)
│  ├─ ee_masking.py          # cloud masking utilities
│  ├─ engine.py              # AnalyticsEngine
│  ├─ results.py             # dataclasses for results
│  ├─ stats.py               # summary stats
│  ├─ timeseries.py          # TimeSeries & decomposition helpers
│  └─ trend.py               # trend fitting
├─ biodiv/
│  ├─ bscore.py              # BScoreCalculator & weights
│  ├─ gbif_validator.py      # occurrence density (optional)
│  └─ metrics.py             # MetricEngine (intactness, shannon, frag_norm)
├─ core/
│  ├─ cli.py                 # CLI entry + commands
│  ├─ config.py              # ConfigManager / validation
│  ├─ logger.py              # JSON logger
│  ├─ pipeline.py            # report pipeline
│  ├─ storage.py             # StorageAdapter, LocalFS, S3Bucket
│  └─ utils.py               # small helpers
├─ geo/aoi.py                # AOI model
├─ ingestion/
│  ├─ downloader.py          # EarthEngineDownloader
│  ├─ eemanager.py           # EarthEngineManager (auth/collections)
│  ├─ earthengine_ingestor.py# EarthEngineIngestor (time series & chips)
│  ├─ indices.py             # spectral index formulas
│  ├─ sensorspec.py          # SensorSpec
│  └─ vector_preprocessor.py # shapefile/KML → clean GeoJSON
├─ project/project.py        # Project model
├─ services/
│  ├─ base.py                # BaseService
│  ├─ bscore.py              # compute_bscores helper
│  ├─ landcover.py           # LandcoverService (Esri 10 m TS)
│  ├─ msa.py                 # MSAService (GLOBIO 2015 mean)
│  ├─ raster_reader.py       # open_dataset with egress budget
│  ├─ raster_utils.py        # convert_to_cog
│  ├─ report.py              # build_report
│  └─ timeseries.py          # download_timeseries
├─ visualization/
│  ├─ chips.py               # ChipExporter / ChipService
│  ├─ report.py              # HTML report builder
│  └─ visualizer.py          # plotting helpers
├─ webapp/
│  ├─ app.py                 # Streamlit entry
│  ├─ components/
│  │  ├─ charts.py           # NDVI decomposition, MSAVI bars
│  │  ├─ kpi_cards.py        # KPI & gauge
│  │  ├─ layout.py           # theme & navbar
│  │  └─ map_widget.py       # Folium+Titiler layers
│  ├─ services/
│  │  ├─ chip_service.py     # EE chip adapter for UI
│  │  ├─ exports.py          # CSV/PDF exports (presigned)
│  │  ├─ project_compute.py  # project‑wide compute orchestrator
│  │  ├─ project_state.py    # state persistence
│  │  └─ r2.py               # **presigned URL** helper (R2)
│  └─ themes/verdesat.css    # branding
└─ docs/                     # this doc, roadmap, dev principles, MODULES.md
```

### 1.2 Capabilities
- **AOI input** via CLI and Streamlit (upload or draw; demo supports 2 AOIs).
- **Data sources**: Esri 10 m LULC (2017–latest), Sentinel‑2 L2A for NDVI/MSAVI.
- **Metrics**: Intactness %, Shannon diversity, Fragmentation (biome‑norm), **B‑Score**.
- **Visuals**: Annual **NDVI/MSAVI composites**, NDVI time‑series decomposition plots, KPI row & gauge.
- **Artifacts**: COGs (rasters), CSV time series, HTML/PDF reports stored in **R2**.
- **Access pattern**: Private R2 bucket; Streamlit signs objects and requests tiles via **Titiler**.

### 1.3 Known gaps
- No persistent **multi‑tenant** data model (Users/Projects/AOIs in DB).
- No **unified HTTP API**; clients call Python services directly.
- No background **job queue**; long jobs can block.
- Basic auth only; no per‑tenant RBAC.

---

## 2) Target Architecture v1.0 (12–16 weeks)

### 2.1 Diagram
```
             +-------------------+        +-------------------+
  CLI  --->  |   FastAPI Core    |  --->  |  Postgres+PostGIS |
 WebApp ---> | (Auth, CRUD, Jobs)|        +-------------------+
             |        |   ^      |
             |        v   |      |
             |    Queue/Events   |
             +--------|----------+
                      v
               +-------------+               +----------------
               |  Workers    | ---- GEE ----> Earth Engine API
               |  (RQ/Celery)| ---- R2  ----> Cloudflare R2 (COGs/CSVs/PDFs)
               +-------------+               +----------------
```

### 2.2 Domain model (DB)
- **User** *(id, email, pw_hash, role, created_at)*
- **Project** *(id, user_id FK, name, created_at)*
- **AOI** *(id, project_id FK, name, geom: geometry(MultiPolygon, 4326), area_ha)*
- **Job** *(id, project_id FK, aoi_id FK NULLABLE, kind, params JSONB, status, started_at, finished_at, cost_ms)*
- **MetricSet** *(id, aoi_id FK, year, payload JSONB — includes NDVI/MSAVI stats & optional MSA, version, created_at)*
- **Artifact** *(id, project_id FK, aoi_id FK NULLABLE, kind, r2_key, mime, bytes, checksum, created_at)*

> **R2 key convention**: `s3://verdesat-data/{project_id}/{aoi_id}/{run_id}/{year}/{KIND}.tif|csv|pdf`

### 2.3 API surface (FastAPI)
- `POST /auth/signup`, `POST /auth/login`
- `POST /projects`, `GET /projects/{id}`
- `POST /projects/{id}/aois` (GeoJSON upload) / `GET /projects/{id}/aois`
- `POST /aois/{id}/runs`  → returns **job_id**
- `GET /jobs/{job_id}`     → status
- `GET /aois/{id}/metrics?year=YYYY` → MetricSet JSON
- `GET /artifacts/{id}`    → presigned URL for COG/CSV/PDF

### 2.4 Processing
- Workers call existing services (MetricEngine, LandcoverService, TimeSeries, MSAService).
- Write **MetricSet** and **Artifact** rows; upload heavy files to **R2**.
- Emit lightweight audit events; ensure idempotency by parameter hashing.

### 2.5 Security
- JWT/Supabase Auth; project‑scoped tenancy; presigned R2 access (15–60 min expiry).
- Basic rate‑limit on `/runs` to protect GEE quotas.

### 2.6 Observability
- JSON logs to stdout; basic request/job metrics; smoke & load tests in CI.

---

## 3) Migration Plan (MVP → v1.0)

**Phase A (Weeks 1–3): Foundations**
- Stand up Postgres/PostGIS (Neon/Supabase/fly.io). Add Alembic migrations.
- SQLAlchemy models for User/Project/AOI/Job/MetricSet/Artifact.
- FastAPI core with Auth & CRUD; wire to DB.

**Phase B (Weeks 4–6): Jobs & Artifacts**
- Introduce Queue (RQ/Redis or Cloudflare Queues) and a Worker container.
- Execute runs via existing engines; write MetricSet JSONB; upload Artifacts to R2 using the key convention.

**Phase C (Weeks 7–9): Unified Clients**
- CLI switches to API (`login`, `aoi upload`, `run`, `metrics fetch`).
- Streamlit reads from API; rasters via `/artifacts/{id}` → presigned URL.

**Phase D (Weeks 10–12): Hardening**
- RBAC basics, rate‑limits, error taxonomy. Load test (50 parallel jobs, P95 < 12 min/1 km² AOI).

---

## 4) Principles we enforce
- **Single source of truth** in Postgres; filenames are not truth.
- **Pure services**, framework‑agnostic; repositories hide the ORM.
- **DTOs** via Pydantic; explicit schemas at the API boundary.
- **Idempotent runs** keyed by (AOI, year, params → hash).
- **12‑factor config** using env/Pydantic; **structured logging**.
- **Tests:** unit (fast, offline) + integration (EE mocked) + e2e on staging.

---

## 5) Cost (indicative)
- Postgres (free tier) — €0
- R2 storage (≈2 TB) — ~$30/mo
- API + Worker on Fly.io (256–512 MB) — €0–€10/mo
- Streamlit Cloud — free for staging; Fly for prod

---

## 6) Open Questions
- Queue choice: Redis/RQ (simple) vs Cloudflare Queues (serverless).
- Auth choice: Supabase vs simple JWT vs OAuth (sales‑friendly).
- Tiling: continue Titiler SaaS vs host a tiny instance.

```
This document is the source of truth for the target architecture and migration plan. Keep it updated when major components land.
```