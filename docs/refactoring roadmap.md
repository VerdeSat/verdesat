1  Modularity & Cohesion — Concrete To-Dos

Module	What to change	Why / Outcome
core	Split utility bloat. If utils.py now mixes string helpers, CloudStorage helpers, and argument parsing, break it into text.py, storage.py, cli_helpers.py.Remove implicit state. If any module-level globals (e.g. EE_PROJECT, DEFAULT_OUTPUT_DIR) still exist, move them behind a Settings object that is created, not imported.Centralise logging. Expose core.logging.get_logger() once; every other module should call that, never instantiate its own logging.Logger.	Keeps each sub-module “about one thing”, prevents unrelated helpers from leaking into every import. High cohesion → easier mental model.
ingestion	Separate “fetch” vs “transform”. Create Downloader classes that only pull raw assets; push cloud-masking, resampling, and chip-cutting to analytics/pre-processing.Factor common retry/progress code into a BaseDownloader. All satellite subclasses inherit; removes duplicated while-loops/back-off logic.Drop local-file assumptions. Downloader returns an in-memory object or URI string, not a fixed ./data/*.tif path.	Eliminates hidden coupling with analytics & CLI; downloader code becomes reusable pipeline component.
analytics	Isolate per-analysis pipelines. Make NdviSeries, WaterSeries, TrendAnalyzer separate files/classes.  The current “kitchen-sink” processor still mixes them.Move chip tiling here – if visualization/chips.py still hosts tile logic, cut-paste into analytics/tiling.py and import from viz when needed.Return typed objects, not file paths. E.g. TrendAnalyzer.run() → TrendResult dataclass with attrs series, trend_img, p_value instead of side-effects into disk.	Each analysis has single ownership; downstream code can compose objects instead of guessing filenames.
CLI (indirect)	Ensure every command calls functions, not other Click commands.  Put the functional core in verdesat.services.* so tests can import them without Click context.	Breaks cyclic dependencies and keeps CLI a thin shell.


⸻

2  Abstraction & OOP — Concrete To-Dos

Area	Improvement	How
Domain objects	Introduce lightweight data-classes:Region(AOI: gpd.GeoSeries, id: str)TimeSeries(df: pd.DataFrame)ChipArray(np.ndarray, meta: dict)	Use @dataclass or pydantic.BaseModel; pass these between layers instead of raw dicts/paths.  Encapsulates data plus validation.
Ingestor hierarchy	Abstract base -> SatelliteIngestor with fetch(aoi, date_range) -> ImageryBatch.Concrete: Sentinel2Ingestor, LandsatIngestor, etc.	Enforces open-closed; adding a new sensor means subclassing, not editing switch-statements.
Strategy pattern for analytics	Define class IndexCalculator(Protocol): compute(img) -> ee.Image.Ship built-ins (NDVI, EVI, etc.) and inject chosen calculator into TimeSeriesBuilder.	Removes hard-coding of NDVI everywhere; easier to extend.
Dependency injection	Pass shared services (Settings, Logger, StorageAdapter) into constructor, do not import them inside methods.	Makes modules testable (mock objects) & stateless.
Encapsulation	Any function mutating the outside world (disk writes, API calls) should live behind a class method with a clear name (StorageAdapter.save_png).	Clarifies side-effects and decouples implementation.
Unit boundaries	No class should exceed ~300 lines or expose >8 public methods; if so, split into collaborators.	Keeps each class focused, aligns with SRP.


⸻

3  Cloud Readiness — Concrete To-Dos

Module / Concern	Concrete change	Reference
Configuration	Replace core/config.py constants with a Settings object that reads only from env vars using e.g. pydantic.BaseSettings; forbid JSON/YAML checked into repo.	Twelve-Factor III. Config  ￼
Statelessness	Purge module-level caches; any long-lived state should live in Redis/S3, or be recomputed. CLI entrypoints create objects, do work, exit.	Twelve-Factor VI. Processes  ￼
Pluggable storage	Introduce StorageAdapter interface with implementations: LocalFS, S3Bucket, GCSBucket.  Accept a URI like s3://bucket/key everywhere instead of naked Path.  Use fsspec under the hood.	Allows same code to run on dev laptop or container without edits.
Logs	Remove every print(); call logging.getLogger(__name__).  Default handler → STDOUT. No file handlers in library code.	Twelve-Factor XI. Logs  ￼
Side-effect segregation	Any networking (EE API, HTTP) behind clients/ abstractions.  Makes it trivial to stub in tests and avoids unexpected calls when imported.	
Container hints	Add a minimal Dockerfile that installs only production deps, sets ENV vars (not copying .env), and runs verdesat via the CLI.  Ensure the app can start with just verdesat --help and exits cleanly.	
Paths & tmp	Replace Path("output") / fname with tempfile.TemporaryDirectory() or a --output-uri option so a read-only container FS works.	
Retry/back-off	Use tenacity or similar in ingestion network code; configure via env (EE_MAX_RETRIES).	


⸻

Quick Hit Checklist (copy into your tracker)
	•	core: split utilities, central logger, remove globals
	•	core: Settings via env variables
	•	ingestion: BaseDownloader + subclasses, move transforms out
	•	ingestion: storage adapter layer (local/S3/GCS)
	•	analytics: one class per analysis, chip tiling relocated here
	•	analytics: return objects, no implicit file IO
	•	chips: unify into analytics/tiling.py, documented, stateless
	•	OOP: Data-classes for Region, TimeSeries, ChipArray
	•	OOP: Strategy pattern for index calculators
	•	Cloud: logging to STDOUT, no prints
	•	Cloud: no hard-coded paths; accept URIs
	•	Docs: add docstrings for every public class/method (PEP 8)  ￼

Tackling the above will lock in high cohesion, low coupling, genuine abstraction, and first-class cloud portability—exactly what you need before refactoring the remaining modules.
Follow-up tasks after second audit
---------------------------------
    • Replace remaining `print` statements with logger calls.
    • Expose `DEFAULT_REPORT_TITLE` via `ConfigManager` and use in CLI defaults.
    • Implement `AnalyticsEngine.compute_trend` or remove the stub.
