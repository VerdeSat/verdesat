# AGENTS.md — Guidance for Codex & Code Assistants (VerdeSat core repo)

This repo is the **core VerdeSat codebase** (CLI + Streamlit webapp + services). Goals: correctness, reproducibility, cloud‑readiness, and maintainability.

## Tech context (read first)
- **Python**: 3.11 (type‑hint everything)
- **Webapp**: Streamlit (keep logic in services, not in UI)
- **Geo stack**: GeoPandas/Shapely 2, Rasterio, rioxarray/xarray (optional), pystac, Folium/Leafmap, GDAL/PROJ
- **Data**: Sentinel‑2/HLS, COG/Parquet/GeoJSON, optional Zarr; GEE (mock in tests)
- **Storage**: via `StorageAdapter` (local, S3‑compatible like Cloudflare R2)
- **Config/Logging**: `ConfigManager`, `Logger`

## Golden rules (hard requirements)
1. **Reuse existing services and abstractions** — `StorageAdapter`, `services.raster_utils.convert_to_cog`, etc. No duplicate utilities.
2. **Dependency injection** — pass services (`ConfigManager`, `Logger`, `StorageAdapter`) via constructors/params; don’t import singletons inside functions.
3. **No direct filesystem/HTTP in domain logic** — all I/O goes through adapters/clients injected at edges.
4. **Typed, documented, deterministic** — full type hints; short docstrings; no global mutable state; pure functions where possible.
5. **Tests before merge** — add/extend pytest coverage; mock GEE and network; deterministic seeds.
6. **Do not change public APIs silently** — if you must, deprecate and update call sites + tests + docs.

## Geospatial pitfalls (follow these or the tests will bark)
- **CRS**: never assume EPSG:4326 for area/length. Use geodesic area helpers or reproject to an equal‑area CRS.
- **Coordinate order**: lon, lat for GeoJSON; watch axis order when converting.
- **NODATA**: propagate consistently; set `nodata` in Rasterio profiles; mask ops must respect nodata.
- **Resampling**: be explicit (`nearest` for categorical; `bilinear/cubic` for continuous). Never default silently.
- **Windowed I/O**: read rasters in windows instead of loading whole arrays for big inputs.
- **File formats**: prefer **COG** for rasters, **Parquet/GeoParquet** for tabular/vector outputs, **GeoJSON** for small AOIs.

## Performance & reliability
- Prefer **vectorized** GeoPandas/Shapely ops. Avoid Python loops over features.
- Use **chunking/tiling** for large rasters; consider `rioxarray` with Dask **only** when needed.
- Implement **retry with exponential backoff** for rate‑limited APIs (e.g., GEE), and keep operations **idempotent**.
- Streamlit **caching**: keys must be stable; avoid capturing unhashables; clear cache on schema changes.

## Testing policy
- Always run `pytest -q` locally. Add tests for new code.
- Mock external systems (GEE, S3/R2) via fixtures/stubs in `tests/`.
- Use **golden files** for small sample rasters/vectors; store under `tests/data/`.
- Consider **property‑based tests** (hypothesis) for geometry validity and CRS round‑trips.
- No network in CI tests. Mark slow/integration tests with `@pytest.mark.slow`.

## Lint/type/tools (expected)
- **Ruff** (lint + isort), **Black** (format), **Mypy** (type check, strict on new modules)
- Pre‑commit hooks should pass before PR.

## Security & secrets
- No credentials in code or tests. Use env vars and `.env.example`.
- Prefer `boto3`/S3 clients via adapters with **least‑privilege** credentials.
- Never `pickle` untrusted data. Validate user uploads and sanitize filenames (no path traversal).

## PR checklist (must include)
- [ ] Tests added/updated and passing locally (`pytest -q`)
- [ ] Types & docstrings present; no new global state
- [ ] No direct I/O bypassing adapters; GEE calls mocked in tests
- [ ] Lint/format/type checks pass (ruff/black/mypy)
- [ ] Performance reasonable (no full‑raster loads unless justified)
- [ ] Docs updated (README/module docs/changelog) if behavior changed

## Common integration patterns
- **New service**: create a class with a single responsibility, DI for config/logger/storage, and a small public API. Add unit tests with fakes.
- **New CLI**: thin wrapper calling the service; batch over all AOIs by default; log via `Logger`.
- **Webapp feature**: UI component calls a service function. Keep state minimal; cache carefully; no heavy work on the main thread.

## Things NOT to do
- Don’t add a second storage layer or bypass `StorageAdapter`.
- Don’t sneak in heavy deps (Spark, Ray, etc.) without discussion.
- Don’t mutate dataframes/arrays in place across module boundaries.
- Don’t rely on GDAL/PROJ upgrades that deviate from the repo’s setup.