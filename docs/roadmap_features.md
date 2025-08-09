
⸻

11) Build Tickets — Compliance & Product (next 2–4 weeks)

**A. Evidence Pack v1 (ESRS/TNFD)**
- Output: single ZIP per AOI containing:
  - `report.pdf` (A4) with sections: Executive summary; KPI strip (B‑Score, Intactness %, Frag‑Norm, NDVI μ/Δ/slope); Risk band (Low/Mod/High); Map figure; WDPA/KBA proximity; **ESRS E4 mapping** (extent/condition/pressures); Methods & Limitations; Data lineage (sources, versions, dates); Appendix with terms.
  - `metrics.csv` (wide table; one row per AOI with KPI values and timestamps).
  - `lineage.json` (schema below).
  - Optional GeoTIFFs: last‑annual NDVI, MSAVI, land‑cover mask; thumbnail PNGs.
  - `method_version.txt` and `report_hash.txt` (SHA‑256 over `metrics.csv`+`lineage.json`).
- UI: **Download pack** button; choose which artifacts to include.
- Acceptance: pack builds in <3 min for demo AOIs; PDF <5 MB; numerical values match UI KPIs.
- Dependencies: KPI pipeline complete; map render; WDPA/KBA query.

**B. Portfolio Runner (batch)**
- CLI: `verdesat batch --portfolio portfolio.jsonl --year_from 2018 --year_to 2025` → builds packs for N AOIs.
- App: Portfolio page (table): AOI | B‑Score | Intactness | Frag‑Norm | NDVI slope | Updated | Download.
- Portfolio summary PDF: histogram of B‑Scores; % by risk band; data freshness; list of AOIs with flags.
- Acceptance: runs 10 AOIs (Mexico demo copies) in <25 min on dev box; graceful retry & per‑AOI logs.

**C. Lineage & Reproducibility**
- Implement `lineage.json` schema:
  ```json
  {
    "aoi_id": "string",
    "processing_time_utc": "ISO8601",
    "sensors": [{"name":"Sentinel-2 L2A","provider":"Copernicus","collection":"S2 SR","date_range":"YYYY-MM-DD/YY-MM-DD","spatial_res_m":10,"cloud_mask":"s2cloudless vX"}],
    "layers": [{"name":"ESRI LULC 10m","v":"2023"},{"name":"MSA GLOBIO 300m","v":"2015"},{"name":"EFA/EFT 300m","v":"<date or NA>"}],
    "operations": [{"op":"NDVI annual composite","method":"median of cloud‑free","params":{"doy":"1–365"}}],
    "weights": {"intactness":0.4,"shannon":0.3,"fragmentation":0.3},
    "valid_obs_pct": 0.0,
    "pixel_counts": {"total": 0, "valid": 0},
    "software": {"verdesat":"v0.1.x","git_commit":"<hash>"}
  }
  ```
- Show lineage panel under the gauge; link to methods anchor.
- Acceptance: JSON validated; shown in app; values change with data window.

**D. Sharing (read‑only)**
- Create **signed share link** endpoint for packs hosted in R2/LocalFS with expiry (e.g., 7–30 days).
- Add read‑only report page (no uploads) that renders PDF preview and exposes artifact links.
- Acceptance: Link opens without auth; expires correctly; access logged.

**E. EUDR Helper Pack**
- Polygon validator: CRS=WGS84, 6‑decimal precision check, self‑intersection fix‑attempt, area calc; polygons >4 ha rule.
- Deforestation check since 2021 per polygon: overlay annual Tree Cover Loss (Hansen); optional GLAD/RADD alerts; generate map tile snapshots and summary table.
- DDS export: `eudr_manifest.csv` + GeoJSON FeatureCollection with required attributes; `archive_policy.json` (5‑year retention toggle).
- Acceptance: Demo polygons pass; artifacts conform to schema; deforestation summary accurate for known test case.

**F. ESRS Framing**
- Add ESRS E4 labels in PDF; add placeholders for E4‑1/2/3/4 narrative text (client‑editable in UI); include “anticipated financial effects” field the client can fill.
- Acceptance: PDF shows ESRS blocks and maps KPIs → extent/condition/pressures table.

**G. EFA/EFT + MSA Integration**
- Ingest EFA/EFT 300 m (10‑day or quarterly composites as available) as **context layer** with AOI aggregation.
- Keep **MSA 2015 (300 m)** as “pressure context” with a bold caveat in PDF.
- Acceptance: toggle appears; AOI summary stats included; caveat text present.

**H. API (stretch)**
- `/score` (POST): body = GeoJSON AOI; returns KPIs + URL to evidence pack.
- `/portfolio` (POST): body = list of AOIs; async job id; polling endpoint.
- Acceptance: works on LocalFS; authenticated via simple token.

**I. Website tasks**
- Add social‑proof strip (Tubosque) + case page updates; Pilot Program section; Investors section tweaks (as drafted above).
- Wire OG/Twitter images and analytics events.

**J. Demo content**
- Package Mexico AOIs (restoration + reference) with captions; sample evidence pack link.

—

12) Data Sources — required/optional

**Core satellite & imagery**
- **Sentinel‑2 L2A** (Copernicus; 10 m; 2017–present) — NDVI/MSAVI composites; cloud mask via s2cloudless. Access: STAC/Earth Engine or AWS/OpenHub.
- **Landsat 8/9 SR** (30 m; 2013–present) — optional backfill for long‑term trends.

**Land cover / habitat**
- **Esri 10 m Land Cover** (2020–2023 annual) — habitat/intactness mask; fragmentation and Shannon.
- **ESA WorldCover 10 m** (2020/2021) — optional cross‑check or fallback.

**Biodiversity / pressure context**
- **GLOBIO MSA 2015** (300 m) — already in use; pressure/intactness context with caveat on vintage.
- **EFA/EFT** (ESA/Copernicus; 300 m; 10‑day or seasonal composites) — functional attributes (productivity/phenology/energy) for context.

**Forest loss & alerts (EUDR support)**
- **Global Forest Change (Hansen) — Tree cover loss** (annual, 2001–present) — deforestation since 2021 check.
- **GLAD deforestation alerts (S2/Landsat)** — near‑real‑time alerts (tropics, optical); optional.
- **RADD radar alerts (S1)** — near‑real‑time alerts (tropics, radar); optional where coverage exists.

**Protected & sensitive areas**
- **WDPA** (UNEP‑WCMC) — monthly updates; polygons and IUCN categories.
- **Key Biodiversity Areas (KBA)** — where license permits; used for proximity/context only.

**Ecoregions & context**
- **WWF Terrestrial Ecoregions** — biome/ecoregion labels per AOI.

**Administrative & basemaps (context only)**
- **Natural Earth / GADM** — admin context in PDF figures.

**Optional enrichment (later)**
- **GBIF occurrences** — validation/context for species presence (screening‑grade only).
- **Human Footprint / Accessibility to Cities** — pressure proxies (disclose limits, older vintages).

**Data handling notes**
- For mixed resolutions (10 m ↔ 300 m ↔ 1 km), compute metrics at **AOI aggregate scale**; report pixel counts and valid‑obs %.
- Track **version & acquisition window** for every dataset in `lineage.json`.
- All third‑party licenses must be honored; KBA use may require explicit permission.