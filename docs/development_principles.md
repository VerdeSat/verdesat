# Development Principles (VerdeSat core)

These principles keep the codebase modular, testable, and cloud‑ready.

## Architecture
- **Layers**
  - **CLI / Webapp**: thin, orchestration only. No business logic.
  - **Services**: domain logic in small classes/functions with clear inputs/outputs.
  - **Adapters**: I/O boundaries (storage, external APIs like GEE). Swap implementations without touching services.
  - **Models/DTOs**: typed data structures for inputs/outputs; avoid passing raw dicts.
- **Composition over inheritance**. Abstract base classes only where multiple implementations are required.
- **Dependency Injection**. Pass `ConfigManager`, `Logger`, `StorageAdapter`, and API clients into constructors.

## Configuration
- No magic constants. Defaults live under `resources/` and are surfaced via `ConfigManager`.
- Support environment overrides; document all settings in README.
- Provide `.env.example` for local dev; never commit real `.env`.

## Logging & Observability
- Use `Logger.get_logger()` exclusively. No `print()`.
- Structure logs with context (project id, AOI, year); prefer JSON in cloud.
- For long jobs, log **start/end**, **timings**, **counts**, and **warnings** (e.g., masked pixels).

## Error handling & resiliency
- Define clear exception types for domain errors (e.g., `InvalidGeometryError`, `RasterReadError`).
- Validate inputs early (CRS present, geometries valid, nodata defined).
- For external calls, implement **retry with backoff** and ensure operations are **idempotent**.

## Storage & data contracts
- All file operations go through `StorageAdapter`. Support at least: local FS and S3‑compatible (Cloudflare R2).
- Use **COG** for rasters; **Parquet/GeoParquet** for tables/vectors; **GeoJSON** only for small AOIs.
- Always write metadata (CRS, transform, nodata) and validate on read.
- Use **windowed reading**/tiling for large rasters; avoid loading full arrays unless necessary.

## Geospatial correctness
- Never compute area/length in EPSG:4326. Use geodesic helpers or equal‑area CRS (e.g., EPSG:8857) depending on task.
- Be explicit about **resampling** (nearest vs bilinear) and document choices.
- Keep coordinate order straight (GeoJSON: lon, lat). Validate bounds.
- Handle `nodata` consistently and propagate masks.

## Performance
- Prefer vectorized operations in GeoPandas/Shapely 2.
- Batch I/O; avoid chatty per‑feature reads.
- Consider `rioxarray/xarray + Dask` for truly large rasters, guarded behind feature flags.
- In Streamlit, cache immutable results with stable keys; avoid caching objects with hidden state.

## Testing
- Unit tests for services and adapters; integration tests for end‑to‑end flows using tiny fixtures in `tests/data/`.
- Mock GEE and S3/R2; no live network in CI.
- Property‑based tests (hypothesis) for geometry validity, CRS round‑trips, and raster windowing invariants.
- Golden files for expected raster/vector outputs where appropriate.

## Style & quality gates
- **Type hints** and short docstrings on all public APIs (numpydoc style preferred).
- **Ruff** (lint + import order), **Black** (format), **Mypy** (strict on new modules).
- Pre‑commit hooks required to pass before merging.
- Conventional Commits; SemVer for releases.

## Adding a new module (how‑to)
1. Sketch the service API (inputs/outputs). Add types.
2. Identify required adapters (storage/API). Implement or reuse them.
3. Write unit tests with fakes/mocks.
4. Implement service logic (vectorized, windowed I/O, explicit resampling).
5. Expose via CLI command (batch over AOIs) and/or Webapp function.
6. Document usage and configuration; update README and changelog.

Adhering to these principles keeps VerdeSat robust, portable, and ready for cloud deployments.