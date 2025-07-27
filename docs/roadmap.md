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

This roadmap should be kept short and updated as features are completed
or added.
