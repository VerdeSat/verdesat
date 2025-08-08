# VerdeSat Modular Architecture Design

_Last updated: 2025-05-29_

---

## 1. Overview

The VerdeSat MVP is structured to enable scalable, modular, and maintainable geospatial analytics for land monitoring. The architecture is built around clearly defined Python classes and modules, each responsible for a narrow domain, to ensure extensibility and clarity.

---

## 1.1 Repository & Modules

```
verdesat/
├─ core/                   # Core utilities, config, logging
├─ project/                # Project and AOI management
├─ geo/                    # Geometry and AOI logic
├─ ingestion/              # Data ingestion backends and sensor specs
├─ analytics/              # Time series and indices processing
├─ modeling/               # Forecasting models (Prophet, LSTM)
├─ visualization/          # Plotting, maps, GIFs, reports
├─ resources/              # Palettes, band maps, formulas (YAML/JSON)
├─ biodiv/
│  ├─ species.py           # Species richness and diversity metrics
│  └─ msa.py                # MSAService: GLOBIO 2015 mean MSA extraction (R2-backed)
├─ webapp/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ components/
│  │  ├─ kpi_cards.py      # KPI cards for NDVI, precipitation
│  │  └─ charts.py          # Matplotlib charts: NDVI decomposition, MSAVI bars
│  └─ utils.py
```

---

## 1.2 Capabilities

- Modular ingestion of EO and ancillary data (Sentinel-2, CHIRPS, ERA5, etc.)
- Time series extraction and gap filling
- Spectral indices calculation (NDVI, MSAVI, EVI, etc.)
- Statistical summaries and annual metrics
- Forecasting via Prophet and LSTM models
- Visualization: static maps, plots, animated GIFs, HTML reports
- **MSA**: Mean Species Abundance (GLOBIO 2015) extraction for AOIs; results stored in R2 and exposed as KPI (optional in v0.1 UI).

---

## 2. Architecture Details

### 2.1 Layered Design

- Data Layer: R2 storage, local cache, cloud buckets
- Ingestion Layer: SensorSpec, DataIngestor subclasses
- Analytics Layer: TimeSeries, AnalyticsEngine, ForecastModel
- Service Layer: Project, AOI, MSAService
- Presentation Layer: Visualizer, Webapp components

---

### 2.2 Domain model (DB)

- Project: client project with metadata and AOIs
- AOI: polygon/multipolygon with static properties and time series data
- TimeSeries: variable, units, frequency, pandas DataFrame
- MetricSet: annual or seasonal summary metrics (includes NDVI/MSAVI stats and optional MSA)
- Artifact: references to files or external data (plots, forecasts, MSA CSVs)

---

### 2.3 Data flow

- Ingest raw data → extract time series → compute indices → fill gaps → summarize → forecast → visualize → export/report

---

### 2.4 Processing

- Time series extraction from Earth Engine or openEO
- AnalyticsEngine applies gap filling, decomposition, trend analysis
- ForecastModel fits and predicts future values
- Visualizer generates plots and GIFs
- MSAService reads pre-staged GLOBIO tiles from R2 (or local cache) and writes per-AOI mean values to MetricSet payload.

---

## 3. Class & Module Outlines

### core/

#### `ConfigManager`
```python
class ConfigManager:
    """
    Loads and manages configuration from file, env, CLI, or defaults.
    Central entry point for all parameterization.
    """
```

#### `Logger`
```python
class Logger:
    """
    Central logging setup, all modules use this for consistent logging.
    """
```

---

### project/

#### `Project`
```python
@dataclass
class Project:
    """Represents a client project with AOIs and project-level metadata."""
    name: str
    customer: str
    aois: List['AOI']
    config: ConfigManager
```

---

### geo/

#### `AOI`
```python
class AOI:
    """
    Area of Interest (AOI): one polygon/multipolygon, with static metadata and time series for each dynamic property.
    """
    def __init__(self, geometry: Polygon or MultiPolygon, static_props: dict, timeseries: Dict[str, TimeSeries] = None):
        self.geometry = geometry
        self.static_props = static_props
        self.timeseries = timeseries or {}

    def add_timeseries(self, variable: str, ts: TimeSeries):
        self.timeseries[variable] = ts
```

---

### analytics/

#### `TimeSeries`
```python
class TimeSeries:
    """
    Holds a time-indexed pandas DataFrame for one variable (e.g., NDVI, precipitation).
    - variable: str
    - units: str
    - freq: str (temporal resolution)
    - df: pd.DataFrame (must have 'date' as index)
    Methods: fill_gaps, decompose, trend, plot, etc.
    """
    def __init__(self, variable, units, freq, df):
        ...
    def fill_gaps(self, method="linear"):
        ...
    def seasonal_decompose(self, period=None):
        ...
```

#### `AnalyticsEngine`
```python
class AnalyticsEngine:
    """
    Collection of static methods for common time series and analytics operations.
    Used by TimeSeries or directly for batch ops.
    """
    @staticmethod
    def compute_trend(ts: 'TimeSeries'):
        ...
```

---

### ingestion/

#### `SensorSpec`
```python
class SensorSpec:
    """
    Contains info about a remote sensing product/collection.
    - bands: Dict[str, str] (e.g., {'nir': 'B8', 'red': 'B4'})
    - native_resolution: int
    - collection_id: str
    - cloud_mask_method: str
    """
    ...
```

#### `DataIngestor`
```python
class DataIngestor:
    """
    Abstract base class for data ingestion. Subclass for EarthEngine, openEO, local, etc.
    """
    def download_timeseries(self, aoi: 'AOI', sensor: 'SensorSpec', index: str, ...):
        raise NotImplementedError()
```

---

### modeling/

#### `ForecastModel` (base class)
```python
class ForecastModel:
    """
    Abstract base for forecasting (Prophet, LSTM, etc).
    """
    def fit(self, timeseries: 'TimeSeries'):
        raise NotImplementedError()
    def predict(self, periods: int):
        raise NotImplementedError()
```

---

### visualization/

#### `Visualizer`
```python
class Visualizer:
    """
    Handles all plotting, static maps, animated GIFs, HTML reports, etc.
    """
    ...
```

---

### resources/

- `palettes.yaml` — Color palettes for spectral indices, user-customizable.
- `sensor_specs.json` — Sensor and band registry (collection IDs, band aliases, native resolutions, cloud-mask methods).
- `index_formulas.json` — List of spectral index formulas (expressions, parameters), user-extendable.

---

## 4. Critical Config Objects

- `config.toml` or `.env` file for global/project-level parameters (default collection, output dirs, logging level, etc.)
- Sensor/band registry (JSON/YAML)
- Palette and index formula registry (JSON/YAML)
- CLI arguments always override config file/env where applicable

---

## 5. Config & Logging Flow

- **ConfigManager** loads config at program start.
- **Logger** initialized in `core`, used everywhere (no direct `print`).
- All class constructors accept config/logging objects or use defaults.
- Most params (collection, scale, bands, output_dir, etc.) are overrideable from CLI.

---

## 6. OOP Best Practices & Recommendations

- Each class should have a single responsibility.
- Favor composition (AOI contains TimeSeries, not inheritance).
- Use abstract base classes for extensibility (e.g., DataIngestor, ForecastModel).
- Avoid global variables/magic constants — use config/resource files.
- All major classes and public methods must have docstrings.
- Don’t over-engineer — keep it clear and pragmatic for actual analytics.

---

## 7. Open Roadmap

The initial refactor has aligned the code with this architecture.
Current backlog items are listed in `roadmap.md`.

---

## 8. Example: Usage Pattern

```python
config = ConfigManager.load("config.toml")
project = Project("ClientXYZ", "Acme Corp", [], config)
aoi = AOI(geometry, {"name": "Field1", "climate_zone": "temperate"})
ts = TimeSeries("ndvi", "unitless", "monthly", df)
aoi.add_timeseries("ndvi", ts)
project.aois.append(aoi)

data_ingestor = EarthEngineIngestor(sensor_spec, config)
data_ingestor.download_timeseries(aoi, sensor_spec, "ndvi", ...)
```

---
# 9. External Solutions Integration

- EODAG: Provides standardized search/download for Sentinel, Landsat, and more. Consider implementing an EODAGDataIngestor to avoid custom download scripts.
- openEO: For future cloud-scale processing, add an OpenEODataIngestor subclass and offer as backend option.
- Index formulas: Move all index calculation formulas to a resource file (JSON/YAML), editable by user. Evaluate [spectral] or other open source registries for expansion.
- Cloud masking: For Sentinel-2, offer s2cloudless as an option. Wrap it as a cloud mask strategy in SensorSpec or DataIngestor.
- Visualization: geemap is recommended for future interactive visualizations in notebooks, but static plotting is prioritized for the CLI MVP.

---
**This architecture supports scalable land/EO analytics, new features, cloud migration, and OOP clarity.**  
Edit and expand as needed!
# VerdeSat Architecture — **Current State, Target v1.0, and Migration Plan**

_Last updated: 2025-08-08_

---

## 0. TL;DR
- **Today (MVP)**: Python monorepo with GEE-backed metrics, COGs on **Cloudflare R2**, and a **Streamlit** dashboard using **presigned URLs**; CLI and modules share the same services.
- **Target v1.0**: One **FastAPI Core** for Users/Projects/AOIs/Jobs/MetricSets, **Postgres + PostGIS** for metadata, **R2** for heavy artifacts, **Workers/Queue** for background processing; Streamlit and CLI become thin clients of this API.
- **Why**: Single source of truth, multi-tenant readiness, cheap to run, easy to extend, cloud-native patterns.

---

## 1. Current State (MVP)

### 1.1 Repository & Modules
```
verdesat/
├─ biodiv/
│  ├─ metrics.py              # MetricEngine: intactness, shannon, fragmentation_norm
│  └─ bscore.py               # BScoreCalculator (YAML weights)
├─ ingestion/
│  └─ landcover_service.py    # Esri 10 m LULC (2017–latest) w/ fallback to WorldCover 2021
├─ analytics/
│  └─ timeseries.py           # TimeSeries, aggregation & decomposition helpers
├─ webapp/
│  ├─ app.py                  # Streamlit entry
│  ├─ components/
│  │  ├─ map_widget.py        # Folium + Titiler tile layers
│  │  └─ kpi_cards.py         # KPI row
│  ├─ services/
│  │  ├─ r2.py                # R2 presigned URL helper (boto3)
│  │  └─ compute.py           # Orchestration for demo metrics & time-series
│  └─ themes/
│     └─ verdesat.css
├─ core/                      # config/logging/cli glue (existing)
└─ docs/
   ├─ architecture.md         # (this doc)
   └─ roadmap.md
```

### 1.2 Capabilities
- **AOI ingest**: GeoJSON upload or draw in the dashboard (2 AOIs demo).
- **Data sources**: Esri 10 m annual LULC (2017–2024), Sentinel‑2 L2A for NDVI/MSAVI.
- **Metrics**: Intactness %, Shannon diversity, Fragmentation (normalized, biome-aware), **B‑Score** (weighted composite).
- **Visuals**: Annual **NDVI/MSAVI composites**, NDVI time‑series decomposition, KPI cards.
- **Artifacts**: GeoTIFF/COG composites, CSV time series, PDFs saved to **R2**.
- **Access pattern**: Streamlit signs private R2 objects and requests tiles via **Titiler**.

### 1.3 Known gaps
- No persistent **multi-tenant** model (Users/Projects/AOIs in a DB).
- No unified **HTTP API**; Streamlit/CLI call Python services directly.
- No background queue; long jobs block a worker.
- AuthZ/AuthN minimal; no per-tenant isolation.

---

## 2. Target Architecture v1.0 (12–16 weeks)

### 2.1 High‑level
```
             +-------------------+        +-------------------+
  CLI  --->  |   FastAPI Core    |  --->  |  Postgres+PostGIS |
 WebApp ---> | (Auth, CRUD, Jobs)|        +-------------------+
             |        |   ^      |
             |        v   |      |
             |    Queue/Events   |
             +--------|----------+
                      v
               +-------------+               +----------------+
               |  Workers    | ---- GEE ----> Earth Engine API
               |  (Celery/RQ)| ---- R2  ----> Cloudflare R2 (COGs/CSVs/PDFs)
               +-------------+               +----------------+
```

### 2.2 Domain model (DB)
- **User** *(id, email, pw_hash, role, created_at)*
- **Project** *(id, user_id FK, name, created_at)*
- **AOI** *(id, project_id FK, name, geom: geometry(MultiPolygon, 4326), area_ha)*
- **Job** *(id, project_id FK, aoi_id FK NULLABLE, kind, params JSONB, status, started_at, finished_at, cost_ms)*
- **MetricSet** *(id, aoi_id FK, year, payload JSONB, version, created_at)*
- **Artifact** *(id, project_id FK, aoi_id FK NULLABLE, kind, r2_key, mime, bytes, checksum, created_at)*

> **R2 key convention**: `s3://verdesat-data/{project_id}/{aoi_id}/{run_id}/{year}/{KIND}.tif|csv|pdf`

### 2.3 API surface (FastAPI)
- `POST /auth/signup`, `POST /auth/login`
- `POST /projects`, `GET /projects/{id}`
- `POST /projects/{id}/aois` (GeoJSON upload) / `GET /projects/{id}/aois`
- `POST /aois/{id}/runs`  → returns **job_id**
- `GET /jobs/{job_id}`     → status
- `GET /aois/{id}/metrics?year=2024` → MetricSet JSON
- `GET /artifacts/{id}`    → returns presigned URL

### 2.4 Processing
- **Workers** pull jobs, call existing `MetricEngine`/`LandcoverService`/timeseries.
- Write **MetricSet** row and **Artifact** rows; upload heavy files to **R2**.
- Emit events to a simple audit log (table or queue).

### 2.5 Security
- JWT or Supabase Auth; per‑user tenancy enforced by **project_id** scoping.
- R2 access via backend **presigned URLs** only; short expiry (15–60 minutes).
- Basic rate limiting on `/runs`.

### 2.6 Observability
- Structured logging (JSON) to stdout; aggregate in Loki/Grafana later.
- Metrics: request timings, job durations, error counts.

---

## 3. Migration Plan (MVP → v1.0)

### Phase A (Weeks 1–3): **Foundations**
- Stand up **Postgres+PostGIS** (Neon/Supabase/fly.io). Add **Alembic** migrations.
- Add SQLAlchemy models for User/Project/AOI/Job/MetricSet/Artifact.
- Create **FastAPI core** with Auth + CRUD endpoints; wire to DB.

### Phase B (Weeks 4–6): **Job system & artifacts**
- Introduce **Queue** (RQ/Redis or Cloudflare Queues).
- Worker container uses existing engines to process jobs.
- Store MetricSet JSONB, upload artifacts to R2 with the **new key scheme**.

### Phase C (Weeks 7–9): **Clients converge**
- **CLI** commands call FastAPI (`login`, `aoi upload`, `run`, `metrics fetch`).
- **Streamlit** reads via API and uses `/artifacts/{id}` → presigned URLs.

### Phase D (Weeks 10–12): **Hardening**
- RBAC (user → project membership), basic rate limits, error taxonomy.
- Smoke tests, load tests (50 parallel jobs on 1 km² AOIs).

---

## 4. “Best Practices” we enforce
- **Single source of truth** in Postgres (no truth in filenames).
- **Pure services** (MetricEngine, LandcoverService) remain framework‑agnostic.
- **DTOs** via Pydantic, explicit repositories (no ORM leaks into services).
- **Idempotent runs** (same AOI/year/params → same R2 path; re‑use artifacts).
- **Config** via Pydantic settings; **12‑factor** envs.
- **Tests**: unit (fast, offline) + integration (EE mocked) + e2e on staging.

---

## 5. Cost profile (ballpark)
- Postgres (Neon free) — €0
- R2 storage 2 TB — ~$30/mo (later tiering)
- API + Worker on Fly.io (256–512 MB) — €0–€10/mo
- Streamlit Cloud — free (staging) / Fly for prod

---

## 6. Open Questions
- Pick **Queue**: Redis/RQ (simple) vs Cloudflare Queues (serverless).
- Choose **Auth**: Supabase vs simple JWT (fast) vs OAuth (sales‑friendly).
- Decide on GIS tiling: stick with Titiler SaaS vs host a tiny instance.

```
**This document describes the intended end‑state and a pragmatic path from today’s MVP without breaking the repo.**
```