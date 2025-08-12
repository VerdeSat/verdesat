# MODULES — Auto-generated overview

_Generated: 2025-08-12T17:03:51Z_

## `verdesat`

## `verdesat.adapters`
> Adapters for external services (APIs, storage, etc.).

## `verdesat.adapters.llm_openai`
> OpenAI client adapter implementing :class:`~verdesat.services.ai_report.LlmClient`.
**Classes**
- `OpenAiLlmClient` — LLM client using the OpenAI Responses API.

## `verdesat.adapters.prompt_store`
> Central store for versioned prompts used by :mod:`ai_report` services.
**Classes**
- `PromptBundle` — Container for the different prompt roles.

**Functions**
- `get_prompts` — Return prompts for *version*.

## `verdesat.analytics`
> Analytics helpers and result data types.

## `verdesat.analytics.ee_chipping`
**Functions**
- `export_chips` — Export chips using ChipService.

## `verdesat.analytics.ee_masking`
**Functions**
- `mask_collection` — Apply the sensor-specific cloud mask to each image in the collection.

## `verdesat.analytics.engine`
> AnalyticsEngine
**Classes**
- `AnalyticsEngine` — Collection of static methods for common Earth Engine analytics operations,

## `verdesat.analytics.results`
**Classes**
- `TrendResult` — Linear trend values for each polygon.
- `StatsResult` — Summary statistics computed for each polygon.

## `verdesat.analytics.stats`
**Functions**
- `compute_summary_stats` — Build per-site summary stats and return them as a :class:`StatsResult`.

## `verdesat.analytics.timeseries`
> Module `analytics.timeseries` provides the TimeSeries class, which wraps
**Classes**
- `TimeSeries` — Pandas DataFrame wrapper for a single variable time series.

## `verdesat.analytics.trend`
**Functions**
- `compute_trend` — Fit a linear trend to each polygon's time series and return a :class:`TrendResult`.

## `verdesat.biodiv`

## `verdesat.biodiv.bscore`
**Classes**
- `WeightsConfig` — Weights for each biodiversity metric.
- `BScoreCalculator` — Compute a composite biodiversity score (0-100).

## `verdesat.biodiv.gbif_validator`
**Classes**
- `OccurrenceService` — Fetch species occurrences from citizen-science portals.

**Functions**
- `plot_score_vs_density` — Plot score versus occurrence density and save to *out_png*.

## `verdesat.biodiv.metrics`
**Classes**
- `LandcoverResult` — In-memory landcover raster.
- `FragmentStats` — Edge density statistics.
- `MetricsResult` — Container for all computed metrics.
- `MetricEngine` — Compute biodiversity metrics from land-cover rasters.

## `verdesat.config`

## `verdesat.core`

## `verdesat.core.cli`
> VerdeSat CLI entrypoint — defines commands for vector preprocessing, time series download,
**Functions**
- `cli` — VerdeSat: remote-sensing analytics toolkit.
- `prepare` — Process all vector files in INPUT_DIR into a single, clean GeoJSON.
- `forecast` — Run forecasting pipelines (Prophet, LSTM, etc.).
- `download` — Data ingestion commands.
- `timeseries` — Download and aggregate spectral index timeseries for polygons in GEOJSON.
- `chips` — Download per-polygon image chips (monthly/yearly composites).
- `landcover` — Download 10 m land-cover rasters for all polygons in GEOJSON.
- `stats` — Statistical operations on time-series data.
- `aggregate` — Aggregate a raw daily time-series CSV to the specified frequency.
- `preprocess` — Data transformation commands (gap-fill, resample, etc.).
- `fill_gaps_cmd` — Interpolate missing values in a time-series CSV.
- `decompose` — Perform seasonal decomposition on a pivoted CSV and save plot.
- `trend` — Compute linear trend for each polygon in a time-series CSV.
- `bscore` — Biodiversity score utilities.
- `compute_bscore` — Compute biodiversity score from a metrics JSON file.
- `bscore_from_geojson` — Compute B-Score for polygons in GEOJSON.
- `msa_cmd` — Compute mean MSA for polygons in GEOJSON.
- `validate` — Occurrence validation utilities.
- `validate_occurrence_density` — Compute occurrence density for AOIs in GEOJSON.
- `visualize` — Visualization commands.
- `plot` — Plot time-series from CSV: interactive HTML or static PNG.
- `animate` — Generate one animated GIF per site by scanning IMAGES_DIR for files matching PATTERN.
- `gallery` — Build a static HTML image gallery from a directory of chips.
- `report` — Report generation commands.
- `report_html` — Generate an HTML report with charts and image chips.
- `report_ai` — Generate AI executive summary for AOI metrics.
- `pipeline` — High-level workflows that glue together multiple commands.
- `pipeline_report` — Run full NDVI → report pipeline in one go.
- `webapp` — Run local Streamlit dashboard.

## `verdesat.core.config`
> core.config
**Classes**
- `ConfigValidationError` — Raised when configuration loading or validation fails.
- `ConfigManager` — Loads and manages configuration from file, environment, CLI, or defaults.

## `verdesat.core.logger`
> Module for centralized, configurable logging across VerdeSat packages.
**Classes**
- `JSONFormatter` — Formatter that outputs log records in JSON format with keys:
- `Logger` — Central logging setup for all modules.

## `verdesat.core.pipeline`
**Classes**
- `ReportPipeline` — Encapsulate the NDVI report workflow.

## `verdesat.core.storage`
> Storage adapter abstractions.
**Classes**
- `StorageAdapter` — Abstract interface for persisting binary data.
- `LocalFS` — Store files on the local filesystem.
- `S3Bucket` — Store files in an S3 bucket using boto3.

## `verdesat.core.utils`
> Utility helpers for core modules.
**Functions**
- `sanitize_identifier` — Return a filesystem-safe version of ``identifier``.

## `verdesat.geo.aoi`
> Module `geo.aoi` defines the AOI (Area of Interest) class, which holds a single
**Classes**
- `AOI` — Area of Interest with static properties and optional time series.

## `verdesat.ingestion`
> Ingestion package with backend factory.
**Functions**
- `create_ingestor` — Factory returning an ingestor instance based on backend name.

## `verdesat.ingestion.base`
**Classes**
- `BaseDataIngestor` — Base interface for data ingestion implementations.

## `verdesat.ingestion.downloader`
**Classes**
- `BaseDownloader` — Abstract downloader with chunking and retry logic.
- `EarthEngineDownloader` — Downloader that fetches index values from Earth Engine.

## `verdesat.ingestion.earthengine_ingestor`
> Earth Engine backend for data ingestion.
**Classes**
- `EarthEngineIngestor` — Handles data ingestion for spectral index time series and image chips.

## `verdesat.ingestion.eemanager`
> Module `ingestion.eemanager` provides the EarthEngineManager class to
**Classes**
- `EarthEngineManager` — Manages interaction with Google Earth Engine: initialization, retries, and collection retrieval.

## `verdesat.ingestion.indices`
> Module `ingestion.indices` provides generic spectral index computation
**Functions**
- `compute_index` — Compute a named spectral index on the given EE Image using the JSON formula.

## `verdesat.ingestion.sensorspec`
> Module `ingestion.sensorspec` defines the SensorSpec class, which encapsulates
**Classes**
- `SensorSpec` — Holds metadata for a sensor (bands, collection ID, etc).

## `verdesat.ingestion.vector_preprocessor`
> Module `ingestion.vector_preprocessor` defines the VectorPreprocessor class,
**Classes**
- `VectorPreprocessor` — Processes vector files in a directory and returns a cleaned GeoDataFrame.

## `verdesat.modeling`

## `verdesat.modeling.classifiers`

## `verdesat.modeling.forecast`
**Classes**
- `ForecastModel` — Abstract base for forecasting (Prophet, LSTM, etc).

## `verdesat.modeling.pipelines`
**Functions**
- `landcover_classifier` — Simple RF pipeline: scaling + random forest.
- `forecasting_pipeline` — Placeholder for time‑series forecasting (Prophet / LSTM / XGBoost).

## `verdesat.project.project`
> Project models for managing client projects and their AOIs.
**Classes**
- `Project` — Lightweight project model holding AOIs and related artefacts.

## `verdesat.schemas`

## `verdesat.schemas.ai_report`
> Data models for AI report generation.
**Classes**
- `MetricsSummary` — Aggregated AOI metrics passed to the language model.
- `TimeseriesRow` — Single observation from the VI time series.
- `AiReportRequest` — Parameters for :class:`AiReportService.generate_summary`.
- `AiReportResult` — Result returned by the AI report service.

## `verdesat.services`
> Lightweight service-layer helpers used by the CLI and tests.

## `verdesat.services.ai_report`
> Service for LLM-based report summaries with caching.
**Classes**
- `LlmClient` — Minimal interface for language model clients.
- `AiReportService` — Create AI-generated summaries for project AOIs.

## `verdesat.services.base`
**Classes**
- `BaseService` — Base class for service helpers.

## `verdesat.services.bscore`
**Functions**
- `compute_bscores` — Compute biodiversity scores for AOIs in ``geojson``.

## `verdesat.services.landcover`
**Classes**
- `LandcoverService` — Retrieve annual land-cover rasters from Earth Engine.

## `verdesat.services.msa`
**Classes**
- `MSAService` — Fetch mean Total MSA values from the Globio dataset.

**Functions**
- `compute_msa_means` — Compute mean MSA values for features in ``geojson``.

## `verdesat.services.raster_reader`
**Classes**
- `EgressBudget` — Simple byte counter to limit remote reads.

**Functions**
- `open_dataset` — Open *uri* within a configured :class:`rasterio.Env`.

## `verdesat.services.raster_utils`
**Functions**
- `convert_to_cog` — Convert *path* GeoTIFF to Cloud Optimized GeoTIFF.

## `verdesat.services.report`
> Service layer wrapping report generation utilities.
**Functions**
- `build_report` — Generate an HTML report and return the output path.

## `verdesat.services.timeseries`
**Functions**
- `download_timeseries` — Download spectral index time series for polygons in *geojson*.

## `verdesat.visualization`

## `verdesat.visualization.chips`
> Module implementing ChipExporter and ChipService for exporting image chips via GEE.
**Classes**
- `ChipExporter` — Responsible for taking a single ee.Image (a composite) and exporting
- `ChipService` — Orchestrates end‐to‐end chip creation:

## `verdesat.visualization.report`
**Functions**
- `build_report` — 

## `verdesat.visualization.visualizer`
**Classes**
- `Visualizer` — Utility class for all visualization helpers.

## `verdesat.webapp`

## `verdesat.webapp.app`
**Classes**
- `StreamlitHandler` — Stream logging records to a Streamlit code block.

**Functions**
- `load_demo_project` — Load demo project from bundled GeoJSON and attach demo rasters.
- `compute_project` — Compute metrics and vegetation indices for *project*.
- `report_controls` — Display controls for generating a project-wide PDF report.

## `verdesat.webapp.components.charts`
**Functions**
- `load_ndvi_decomposition` — Load NDVI decomposition CSV for ``aoi_id`` from R2.
- `load_msavi_timeseries` — Load MSAVI time series CSV from R2.
- `ndvi_decomposition_chart` — Render NDVI observed, trend and seasonal curves.
- `msavi_bar_chart` — Render annual mean MSAVI as a bar chart.
- `ndvi_component_chart` — Plot a single NDVI ``component`` for all AOIs.
- `msavi_bar_chart_all` — Render annual mean MSAVI for all AOIs as grouped bars.

## `verdesat.webapp.components.kpi_cards`
**Classes**
- `Metrics` — Container for biodiversity metrics.

**Functions**
- `aggregate_metrics` — Return mean values for ``df`` as a :class:`Metrics` instance.
- `display_metrics` — Render KPI cards for the provided metrics.
- `bscore_gauge` — Display a gauge chart for the B-Score, with risk band and formula explanation.

## `verdesat.webapp.components.layout`
**Functions**
- `apply_theme` — Inject fonts, colors, and base CSS matching VerdeSat branding.
- `render_navbar` — Render the fixed top navigation bar and sidebar-toggle stub inside it.
- `render_hero` — Display a full-width hero banner with ``title`` and optional ``subtitle``.

## `verdesat.webapp.components.map_widget`
> Utilities for rendering project maps in the dashboard.
**Functions**
- `display_map` — Render Folium map with AOI boundaries, metrics and VI layers.

## `verdesat.webapp.services.chip_service`
**Classes**
- `EEChipServiceAdapter` — Download NDVI and MSAVI annual composites for a single AOI.

## `verdesat.webapp.services.exports`
**Functions**
- `export_metrics_csv` — Serialize ``metrics`` for ``aoi`` to CSV and return a presigned URL.
- `export_project_csv` — Export aggregated ``metrics`` for ``project`` and return a URL.
- `export_project_pdf` — Render project metrics, map and charts as a PDF and return a URL.
- `export_metrics_pdf` — Render ``metrics`` and visuals for ``aoi`` as a PDF and return a URL.

## `verdesat.webapp.services.project_compute`
**Classes**
- `ChipService` — Protocol for services providing chip downloads.
- `ProjectComputeService` — Compute metrics and vegetation indices for an entire project.

## `verdesat.webapp.services.project_state`
> Helpers for persisting project state.
**Functions**
- `persist_project` — Persist ``project`` definition using ``storage`` and return its URI.

## `verdesat.webapp.services.r2`
> verdesat.webapp.services.r2
**Functions**
- `signed_url` — Generate a presigned URL for *key* in the bucket defined by R2_BUCKET.
- `upload_bytes` — Upload ``data`` to R2 under ``key``.
