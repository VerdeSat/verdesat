AI Report Summary Module — Specification (VerdeSat)

Last updated: 2025-08-11

Implementation notes: schemas use dataclasses rather than Pydantic, and
configuration keys follow snake_case names (ai_report_model, etc.).

0) Purpose & Scope

Generate customer-facing report summaries (ESRS/TNFD-aligned, screening-grade) from pre-computed metrics and VI time series. The module must:
	•	Ingest summarized AOI metrics and VI time series (CSV/Parquet).
	•	Produce deterministic, structured outputs (JSON) + short narrative blocks for PDF/HTML.
	•	Be callable from CLI and Webapp via the current codebase and migrate cleanly to the Target v1.0 FastAPI/Workers architecture.
	•	Store artifacts in R2 (and/or local cache) and expose lineage & reproducibility metadata.
	•	Avoid raw heavy rasters; use only small summary tables and metadata.

Non-goals (v1): no cron scheduling; no raw imagery analysis inside LLM; no client-editable prompt builder UI.

⸻

1) Architecture Fit & Responsibilities

1.1 Module placement

verdesat/
├─ services/
│  └─ ai_report.py          # AiReportService (public API)
├─ adapters/
│  ├─ llm_openai.py         # OpenAI client adapter (Responses API + Structured Outputs)
│  └─ prompt_store.py       # Versioned prompt templates
├─ schemas/
│  └─ ai_report.py          # Dataclass models for inputs/outputs
├─ core/
│  └─ pipeline.py           # will call AiReportService in Evidence Pack step
└─ tests/
   └─ services/test_ai_report.py

1.2 Public API (Python)

class AiReportService:
    def __init__(self, llm: LlmClient, storage: StorageAdapter, logger: Logger, config: ConfigManager):
        ...

    def generate_summary(
        self,
        *,
        aoi_id: str,
        project_id: str,
        metrics_path: str,        # CSV/Parquet (AOI-level metrics, single row)
        timeseries_path: str,     # CSV/Parquet (date, metric_name, value)
        lineage_path: str | None = None,  # JSON with sensor/layer/version window
        model: str | None = None,
        prompt_version: str | None = None,
        force: bool = False,
    ) -> "AiReportResult":
        """Creates/returns cached LLM summary + deterministic JSON + snippets for PDF."""

1.3 Integration points
	•	MVP (today): called from services/report.py just before HTML/Jinja render to fill Executive Summary, ESRS blocks, KPI wording.
	•	Target v1.0: the FastAPI Worker invokes AiReportService.generate_summary() after a MetricSet is produced. Artifact rows are written and presigned R2 URLs returned by API (GET /artifacts/{id}).

⸻

2) Data Contracts (Inputs)

2.1 Metrics summary (CSV/Parquet)

Single row per AOI. Required columns (lowercase, snake_case):

aoi_id, project_id, method_version, window_start, window_end,
intactness_pct, frag_norm, shannon, bscore,
ndvi_mean, ndvi_slope_per_year, ndvi_delta_yoy,
valid_obs_pct, pixel_count_total, pixel_count_valid,
msa_mean_2015, landcover_mode, landcover_entropy,
wdpa_inside, nearest_pa_name, nearest_pa_distance_km,
nearest_kba_name, nearest_kba_distance_km,
area_ha, centroid_lat, centroid_lon, ecoregion, elevation_mean_m, slope_mean_deg

Notes: values absent → NaN allowed. Schemas implemented via dataclasses in
schemas/ai_report.py; validation occurs in the service layer.

2.2 Time series (CSV/Parquet)

Long format with multiple metrics permitted; must include NDVI.

columns: [date (ISO8601), metric (str), value (float), aoi_id]
required metrics: ndvi_mean (monthly or better)
optional metrics: msavi_mean, evi_mean, rainfall_mm, temp_c

2.3 Lineage (JSON)

lineage.json per roadmap (“C. Lineage & Reproducibility”). If missing, AiReportService will synthesize minimal lineage from arguments.

⸻

3) LLM Invocation Strategy (OpenAI)

3.1 Client adapter
	•	Use OpenAI Responses API with Structured Outputs (JSON Schema) to guarantee a strict output schema.
	•	Prefer model gpt-4o (narrative quality) or gpt-4o-mini (cheap) — configurable.
	•	Determinism settings: temperature=0, top_p=1, seed set via config.
	•	Enforce response_format = JSON-schema; reject on validation error and retry once with guardrails.

3.2 File limits & size discipline
	•	Direct file inputs to Responses API are small; keep each payload < 10 MB, or embed tables inline as text chunks. For larger artifacts, switch to Assistants File Search/Code Interpreter where per-file limit is 512 MB.
	•	Keep tokens tight: send only the final AOI metrics row + 12–24 months of VI summary (aggregated).

3.3 Prompting pattern (versioned)
	•	System: objective, screening-grade, no speculation, ESRS E4 mapping, cite numeric values with keys (e.g., ndvi_mean=0.57).
	•	Developer: schema, allowed claims, forbidden claims (species counts, legal conclusions), rounding rules, unit policy (metric), and wording constraints.
	•	User content: the AOI metrics row + short derived facts (computed locally), and an instruction to produce ai_report.v1 JSON.

Store prompts under adapters/prompt_store.py with a PROMPT_VERSION constant; include in cache key.

3.4 Output schema (ai_report.v1)

{
  "type": "object",
  "required": ["executive_summary", "kpi_sentences", "esrs_e4", "flags", "numbers", "meta"],
  "properties": {
    "executive_summary": {"type": "string", "maxLength": 1200},
    "kpi_sentences": {
      "type": "object",
      "required": ["bscore", "intactness", "fragmentation", "ndvi_trend"],
      "properties": {
        "bscore": {"type": "string", "maxLength": 280},
        "intactness": {"type": "string", "maxLength": 280},
        "fragmentation": {"type": "string", "maxLength": 280},
        "ndvi_trend": {"type": "string", "maxLength": 280}
      }
    },
    "esrs_e4": {
      "type": "object",
      "required": ["extent_condition", "pressures", "targets", "actions", "financial_effects"],
      "properties": {
        "extent_condition": {"type": "string", "maxLength": 700},
        "pressures": {"type": "string", "maxLength": 700},
        "targets": {"type": "string", "maxLength": 500},
        "actions": {"type": "string", "maxLength": 500},
        "financial_effects": {"type": "string", "maxLength": 500}
      }
    },
    "flags": {
      "type": "array",
      "items": {"type": "string", "maxLength": 180},
      "maxItems": 10
    },
    "numbers": {
      "type": "object",
      "description": "Echo back all numeric values actually used in text for auditability",
      "additionalProperties": {"type": ["number", "string", "null"]}
    },
    "meta": {
      "type": "object",
      "required": ["model", "model_revision", "prompt_version", "seed", "input_hash"],
      "properties": {
        "model": {"type": "string"},
        "model_revision": {"type": "string"},
        "prompt_version": {"type": "string"},
        "seed": {"type": "integer"},
        "input_hash": {"type": "string"}
      }
    }
  }
}


⸻

4) Reproducibility & Guardrails
	1.	Determinism: temperature=0, fixed seed, fixed model/version, fixed prompt version; capture system_fingerprint if provided.
	2.	Input hashing: SHA-256 over (metrics.csv bytes + ts.csv bytes + lineage.json bytes + prompt_version + model) → input_hash. Included in output meta and artifact filenames.
	3.	Claim checker (local): after LLM returns JSON, a Python validator recomputes:
	•	trend sign vs ndvi_slope_per_year threshold (±0.002).
	•	closure status if ndvi_mean >= 0.5 for ≥2 consecutive months.
	•	banding: B-Score → Low/Moderate/High.
On mismatch, rewrite specific sentences with templated, rule-based phrasing.
	4.	Numeric echo: require numbers map to contain every number present in text; compare to inputs (±0.001 tolerance). Reject otherwise.
	5.	Length & style caps: enforce max chars per field as in schema; strip any non-ASCII control chars.

⸻

5) Storage, Caching, and Keys
	•	Artifact types: ai_summary.json (strict schema), ai_summary.txt (flattened narrative), optional ai_summary.pdf (rendered using templates).
	•	R2 key pattern:

s3://verdesat-data/{project_id}/{aoi_id}/{run_id}/reports/ai/{model}/{prompt_version}/{input_hash}/ai_summary.json

	•	Cache lookup order: (1) local disk tmp (by hash) → (2) R2 (by key). If found, bypass LLM.
	•	DB (target v1.0): create Artifact row referencing R2 key; attach bytes, checksum, and mime.

⸻

6) FastAPI Surface (target v1.0)

POST /ai-report/generate
  body: { aoi_id, project_id, metricset_artifact_id | metrics_url, ts_url, lineage_url?, model?, prompt_version? }
  202: { job_id }

GET  /ai-report/jobs/{job_id}
  200: { status: queued|running|done|error, artifact_id?, error? }

GET  /ai-report/{aoi_id}/latest
  200: { artifact_id, url (presigned), meta }

Auth: same JWT/project-scoped model as in Architecture doc. Rate-limit /generate.

⸻

7) CLI Surface (MVP)

verdesat report ai \
  --project <id> --aoi <id> \
  --metrics <path.csv|parquet> --timeseries <path.csv|parquet> \
  [--lineage lineage.json] [--model gpt-4o] [--prompt v1] [--force]

Prints artifact path/URL and summary.

⸻

8) Prompts (stored in code, versioned)

8.1 System (excerpt)

You are an environmental reporting assistant generating screening-grade summaries for forest/land restoration AOIs. No speculation. Use only the numbers provided. Cite all numbers in the numbers object. Map KPIs to ESRS E4 terms (extent/condition/pressures/targets/actions/financial effects). Keep wording sober and auditable. Metric units are metric. Do not invent species lists or legal compliance status.

8.2 Developer (rules)
	•	Rounding: percentages to 0.1 pp; NDVI to 0.001; distances to 0.01 km; areas to 0.01 ha.
	•	Trend language: if abs(ndvi_slope_per_year) < 0.002 → “stable”.
	•	Bands: B-Score ≥70 → Low risk; 40–69 → Moderate; <40 → High.
	•	Always include data window (window_start → window_end).

8.3 User payload template

AOI {{aoi_id}} ({{project_id}})
WINDOW: {{window_start}} → {{window_end}}
METRICS ROW:
{{metrics_row_csv}}
TIME SERIES (ndvi; YYYY-MM, value):
{{small_table}}
CONTEXT: {{ecoregion}}, elevation_mean_m={{elevation_mean_m}}, wdpa_inside={{wdpa_inside}}
Produce JSON conforming to schema ai_report.v1 only.


⸻

9) Acceptance Criteria
	•	Functional:
	•	Given valid inputs, AiReportService.generate_summary() returns JSON matching schema and passes claim checker.
	•	Evidence Pack renders with populated Executive Summary and ESRS sections; totals match UI KPIs exactly.
	•	Performance: LLM call completes in < 8 s P95 with gpt-4o-mini and < 20 s with gpt-4o (inputs < 100 kB).
	•	Reproducibility: Same inputs + same config produce identical ai_summary.json (byte-for-byte) in ≥ 19/20 runs.
	•	Storage: Artifacts uploaded to R2 with correct key; presigned URL works for 15–60 min.
	•	Errors: Invalid schema or numeric mismatch triggers a clear error with remediation hints.

⸻

10) Testing
	•	Unit: prompt assembly (golden text), schema validation, claim checker paths, hash computation.
	•	Integration: use small fixtures under tests/data/ and mock OpenAI to return deterministic JSON; also a live test behind env flag.
	•	E2E (optional): CLI → artifact on local FS; compare to golden ai_summary.json.

⸻

11) Config & Secrets
	•	AI_REPORT_MODEL (default: gpt-4o-mini), AI_REPORT_SEED (default: 42), AI_REPORT_PROMPT_VERSION (default: v1) via env vars; ConfigManager keys are ai_report_model, ai_report_seed, ai_report_prompt_version.
	•	OPENAI_API_KEY via env. No keys in repo.
	•	Max input sizes: enforce 10 MB per request (Responses API). For larger tables, down-select columns or pre-aggregate.

⸻

12) Inputs — Existing vs New

12.1 Existing (already in repo / roadmap)
	•	NDVI/MSAVI time series (monthly) per AOI.
	•	KPI table: B-Score, Intactness %, Frag-Norm, NDVI mean/Δ/slope, % valid obs.
	•	MSA 2015 (300 m) mean over AOI (pressure context).
	•	Esri 10 m Land Cover aggregations: mode, diversity (Shannon), fragmentation.
	•	area_ha


12.2 New_Tier_1 (high impact, easy, free/cheap)
	•	WDPA/KBA proximity (inside flag + distances).
	•	WWF Ecoregion label, centroid, elevation_mean_m, slope_mean_deg.
	•	Lineage.json per AOI.	•	CHIRPS rainfall anomalies (monthly) → couple NDVI to water stress.
	•	MODIS MCD64A1 Burned Area frequency since 2015 → fire pressure.
	•	VIIRS Night-lights trend → human pressure proxy (disclose limits).
	•	SoilGrids v2.0 basic properties (e.g., SOC, texture classes) at 250 m → soil context.
	•	SRTM void-filled DEM roughness index → fragmentation/terrain stress.
	•	GLAD (optical) & RADD (radar) alerts counts since 2021 → disturbance context (EUDR helper).

12.3 New_Tier_2 (nice to have / lower impact or costly)
	•	Planet NICFI monthly basemaps (tropics; license gating) → visual evidence.
	•	PlanetScope/Skysat tasking for audits (paid).
	•	GEDI L4A Canopy Height / AGB (coverage gaps) → condition context.
	•	Dynamic World v2 (10 m) for land-cover dynamics vs Esri.
	•	Accessibility to Cities / Human Footprint 2018 as legacy pressure proxies (clearly caveated).
	•	TROPOMI NO₂ for air-pollution context (urban/peri-urban AOIs).

⸻

13) Implementation Plan (2 sprints)

Sprint 1 (setup & MVP path)
	•	Create schemas and service skeleton; implement OpenAI adapter with Structured Outputs.
	•	Prompt v1; hashing; cache → local FS.
	•	Hook into Evidence Pack builder to fill Executive/ESRS blocks.
	•	Unit tests + one live smoke test (env-guarded).

Sprint 2 (hardening & API path)
	•	Add claim checker and numeric echo; R2 storage; presigned URLs.
	•	CLI command verdesat report ai.
	•	(Target) FastAPI endpoints and Worker glue (behind feature flag until v1.0 lands).
	•	Load tests on 10 AOIs; cost/time budget metrics.

⸻

14) Compliance & Wording Guidelines (ESRS/TNFD)
	•	Label outputs “screening-grade; field validation recommended”.
	•	Map KPIs to ESRS E4 sections; provide placeholders for targets/actions/financial effects (client-editable via UI).
	•	Always include data window, versions, and lineage. No claims of species presence or legal compliance.

⸻

15) Observability & Costing
	•	Log: model, latency ms, input bytes, output tokens, retry count, cache hit/miss, input_hash.
	•	Emit basic metrics (Prometheus): ai_report_latency, ai_report_cache_hits, ai_report_errors_total.
	•	Budget: choose gpt-4o-mini for routine runs; switch to gpt-4o for investor decks.

⸻

16) Failure Modes & Fallbacks
	•	Schema invalid → retry once with stricter instructions; else return error with debug payload.
	•	Numeric mismatch → regenerate with tightened developer prompt; else use rule-based templates only.
	•	File too large → down-sample or switch to File-Search path.

⸻

17) Security
	•	No PII. AOI identifiers are project-scoped. R2 artifacts presigned (15–60 min). Do not log actual content of summaries at INFO level.

⸻

18) References
	•	Structured Outputs guide (JSON Schema) and intro.  ￼ ￼
	•	Determinism/seed guidance (advanced usage + cookbook).  ￼ ￼
	•	Assistants tools (File Search/Code Interpreter) overview.  ￼
	•	File size limits (Responses file inputs vs. Assistants/File Search; general uploads FAQ).  ￼ ￼

⸻