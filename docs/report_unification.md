

# VerdeSat — Unified Reporting Specification (v0.2)

**Goal:** replace the three parallel reporting paths with a single, extensible system that feeds both **CLI** and **Web**. No backward compatibility needed. Canonical data model is **snake_case**. Reports may render **UI labels** via a mapping layer.

---

## 1) Decisions (non‑negotiable)
- **Single render engine:** HTML/Jinja2 → **WeasyPrint PDF**. (ReportLab remains an optional fallback only.)
- **One pack format:** **Evidence Pack (AOI)** and **Project Pack** as **ZIPs** with `report.pdf`, `metrics.csv`, `lineage.json`, and a `figures/` directory.
- **Canonical schema:** all inputs to the renderer use **snake_case**.
- **Label mapping:** templates map `snake_case → UI label` for human‑readable captions.
- **Storage abstraction:** use **StorageAdapter** (LocalFS or R2) selected by config.
- **Extendable data model:** `Project/AOI/Timeseries` get light changes to support future variables (climate zone, country, weather, etc.).

---

## 2) Canonical Data Model

> All fields optional unless stated.

### 2.1 ProjectContext
```python
@dataclass
class ProjectContext:
    project_id: str
    project_name: str
    owner: str | None = None
    created_at_utc: str | None = None  # ISO8601
    # Static context (extendable)
    countries_iso3: list[str] | None = None
    primary_country_iso3: str | None = None
    climate_zones: list[str] | None = None      # Köppen codes present across AOIs
    ecoregions: list[str] | None = None         # WWF names/ids
```

### 2.2 AOIContext (static AOI metadata)
```python
@dataclass
class AoiContext:
    aoi_id: str
    aoi_name: str | None = None
    project_id: str | None = None
    geometry_path: str | None = None  # GeoJSON path or URI
    centroid_lon: float | None = None
    centroid_lat: float | None = None
    area_ha: float | None = None
    country_iso3: str | None = None
    admin1: str | None = None
    admin2: str | None = None
    biome: str | None = None          # WWF biome
    ecoregion: str | None = None      # WWF ecoregion
    climate_zone: str | None = None   # Köppen (e.g., Csa)
    tags: dict[str, str] | None = None
```

### 2.3 MetricsRow (single AOI snapshot)
```python
@dataclass
class MetricsRow:
    # Vegetation
    ndvi_mean: float | None = None
    ndvi_slope: float | None = None       # per year
    ndvi_delta: float | None = None       # last_year - prev_year
    msavi_mean: float | None = None
    # Biodiversity proxies
    intactness_pct: float | None = None
    frag_norm: float | None = None
    shannon: float | None = None
    # Composite
    bscore: float | None = None           # 0..100
    bscore_band: str | None = None        # "low|moderate|high"
    # Validity
    valid_obs_pct: float | None = None
    # Sensitivity context
    inside_pa: bool | None = None
    nearest_pa_name: str | None = None
    nearest_pa_distance_km: float | None = None
    nearest_kba_name: str | None = None
    nearest_kba_distance_km: float | None = None
    # Time window used
    window_start: str | None = None
    window_end: str | None = None
```

### 2.4 TimeseriesLong (multi‑variable)
**Long format** suitable for plotting and LLM summaries.
```text
columns: [date, var, stat, value, aoi_id, freq, source]
  - date: ISO date (UTC)
  - var: e.g., ndvi | msavi | t2m | precip
  - stat: raw | mean | median | std | trend | seasonal | anomaly | rolling_90d
  - value: float
  - aoi_id: str
  - freq: monthly | 10day | daily | annual
  - source: e.g., S2 | Landsat | ERA5 | EFA | MSA
```

### 2.5 Lineage (JSON)
```json
{
  "method_version": "0.2.0",
  "code_version": "<git_sha>",
  "config_hash": "<sha256>",
  "window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "sources": [
    {"name":"Sentinel-2 L2A","version":"v2024","resolution":"10 m","date_range":"2017–present","notes":"NDVI/MSAVI composites"},
    {"name":"Esri LULC 10 m","version":"2023","date_range":"2020–2023"},
    {"name":"GLOBIO MSA","version":"2015","resolution":"300 m","date_range":"2015","notes":"pressure context"},
    {"name":"EFA/EFT","version":"current","resolution":"300 m","date_range":"rolling"}
  ],
  "pixel_counts": {"total": 0, "valid": 0},
  "masks": {"cloud": "s2cloudless vX"}
}
```

### 2.6 UI Label Mapping (for templates)
```python
LABELS = {
  "ndvi_mean": "NDVI μ",
  "ndvi_slope": "NDVI slope/yr",
  "ndvi_delta": "ΔNDVI (YoY)",
  "msavi_mean": "MSAVI μ",
  "intactness_pct": "Intactness %",
  "frag_norm": "Frag‑Norm",
  "shannon": "Shannon H′",
  "msa": "MSA",
  "bscore": "B‑Score",
  "bscore_band": "B‑Score band",
  "valid_obs_pct": "% valid obs"
}
```

---

## 3) File/Artifact Formats

### 3.1 Evidence Pack ZIP (AOI)
```
results/projects/{project_id}/aoi_{aoi_id}/evidence_pack_{ts}.zip
  ├─ report.pdf
  ├─ metrics.csv                 # 1 row; snake_case headers
  ├─ lineage.json
  └─ figures/
       ├─ map.png
       └─ timeseries.png
```

### 3.2 Project Pack ZIP
```
results/projects/{project_id}/project_pack_{ts}.zip
  ├─ project.pdf
  ├─ metrics.csv                 # many AOIs (one row each)
  ├─ lineage.json
  └─ figures/
       └─ timeseries.png         # aggregate trend
```

### 3.3 CSV Schemas
- `metrics.csv` (AOI): headers = **snake_case** fields from `MetricsRow` + `aoi_id`, `aoi_name`.
- `project metrics.csv`: one row per AOI; include `aoi_id`, `aoi_name` + KPIs.
- `timeseries.csv`: `date,var,stat,value,aoi_id,freq,source`.

---

## 4) One Reporting Service (library; no UI)

**Module:** `verdesat/services/reporting.py`

```python
@dataclass
class PackResult:
    uri: str
    url: str | None
    sha256: str
    bytesize: int

def build_aoi_evidence_pack(
    *, aoi: AoiContext, project: ProjectContext,
    metrics: MetricsRow, ts_long: pd.DataFrame,
    lineage: dict, include_ai: bool = False,
    storage: StorageAdapter | None = None,
    template: str = "evidence_pack.html.j2",
) -> PackResult: ...

def build_project_pack(
    *, project: ProjectContext, metrics_df: pd.DataFrame,
    ts_long: pd.DataFrame | None, lineage: dict,
    storage: StorageAdapter | None = None,
    template: str = "project_pack.html.j2",
) -> PackResult: ...
```

**Responsibilities:**
- Validate inputs against schemas.
  - Generate figures (`figures/map.png`, `figures/timeseries.png`).
- Render PDF via Jinja2 + WeasyPrint.
- Compose ZIP + upload via `StorageAdapter` (LocalFS/R2).
- Return `PackResult` (including presigned URL when R2).

**Optional AI summary:**
- If `include_ai=True`, call `verdesat/services/ai_report.generate_summary(...)` and embed the narrative in the Executive Summary; save the full JSON to `ai_summary.json`.

---

## 5) Thin Interfaces

### 5.1 CLI
```
verdesat pack aoi \
  --aoi-id 12 \
  --metrics metrics.csv \
  --ts timeseries.csv \
  --lineage lineage.json \
  --out r2 [--include-ai]

verdesat pack project \
  --metrics project_metrics.csv \
  --ts project_ts.csv \
  --lineage lineage.json \
  --out r2
```

### 5.2 Web (bridge)
- `webapp/services/reporting_bridge.py` converts current app state to DTOs and calls `build_aoi_evidence_pack(...)`.
- Streamlit gets back a presigned URL.

---

## 6) Refactor Plan (modules that **produce** inputs)

1) **Timeseries & Decomposition**
   - Emit **TimeseriesLong**: `date,var,stat,value,aoi_id,freq,source`.
   - NDVI/MSAVI → `var` = `ndvi|msavi`, `stat` = `raw|trend|seasonal|anomaly`.
   - Weather (future) → `var` = `t2m|precip|vpd`, consistent `freq`.
   - Provide `decomp_to_long(df, aoi_id)` to convert existing seasonal/trend outputs.

2) **Biodiversity Metrics**
   - Produce a `MetricsRow` per AOI; keep **snake_case** only.
   - Implement `ui_metrics_to_dto(mapping)` helper to absorb legacy UI‑style dicts if any linger.

3) **Images/Plots**
   - Centralize in `verdesat/visualization/` with two functions: `make_map_png(aoi_ctx, layers)` and `make_timeseries_png(ts_long)` returning `bytes`.

4) **Project/AOI classes**
   - **Adopt** existing `Project` and `AOI` but extend with optional static fields:
     - `Project`: `countries_iso3`, `climate_zones`, `ecoregions` (computed roll‑up ok).
     - `AOI`: `country_iso3`, `admin1`, `admin2`, `biome`, `ecoregion`, `climate_zone`, `centroid`, `area_ha`.
   - Add builder to derive these from geometry when available (later).

5) **Remove duplicate exporters**
   - Keep the unified service only. Mark legacy HTML/ReportLab paths for deletion after one release.

---

## 7) Templates (single source of truth)
- Store **HTML** + **print CSS** in `docs/reporting_templates.md`.
- Evidence Pack template id: `evidence_pack_report.html.j2`.
- Project Pack template id: `project_pack_report.html.j2` (to add).
- Renderer extracts fenced code blocks.

---

## 8) Acceptance Criteria
- Given a `MetricsRow` and `TimeseriesLong` for the Mexico demo AOI, `build_aoi_evidence_pack(...)` returns a ZIP in < 3 min with a valid `report.pdf`, correct labels, and non‑empty `lineage.json`.
- CLI builds the same ZIP as the Web bridge for the same inputs (byte‑identical except timestamps).
- All field names in `metrics.csv` are **snake_case**. No UI labels leak into CSV/JSON.

---

## 9) Open Items (future)
- Add **EUDR pack** variant (`eudr_report.html.j2`) using the same service.
- Support additional variables in `TimeseriesLong` (ERA5 weather, EFT/EFA indices).
- Optional `ai_summary.json` artifact in the ZIP.

---

## 10) Task List (1–2 sprints)
- [x] Implement DTOs (`schemas/reporting.py`) + `LABELS` mapping.
- [x] Implement `services/reporting.py` with WeasyPrint renderer and StorageAdapter use.
- [x] Add `figures/` helpers for map/timeseries.
- [x] Refactor timeseries/decomposition emitters to **TimeseriesLong**.
- [ ] Refactor KPI builder to output **MetricsRow**.
- [ ] Implement CLI `verdesat pack aoi|project`.
- [ ] Implement Web bridge and button.
- [ ] Remove/deprecate legacy exporters.
