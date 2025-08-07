![CI](https://github.com/VerdeSat/verdesat/actions/workflows/ci.yml/badge.svg)
# VerdeSat — Remote Sensing for Sustainability

VerdeSat is a lightweight geospatial analytics toolkit.  It focuses on
Earth‑observation data ingestion and simple reporting workflows.  The
codebase is built around small, well tested Python classes so that
components can be reused in larger pipelines.

## 🌱 Mission
- Leverage satellite imagery to support sustainable land management and
  biodiversity conservation.

## 🚀 Quickstart
```bash
# Clone and install
git clone https://github.com/verdesat/verdesat.git
cd verdesat
./setup.sh

# Run an end‑to‑end NDVI report (HTML output under ./verdesat_output)
verdesat pipeline report \
  --geojson path/to/regions.geojson \
  --start 2020-01-01 \
  --end 2020-12-31 \
  --out-dir verdesat_output
```

### GeoJSON project metadata
GeoJSON uploads may include a top-level `metadata` object to describe the
project:

```json
{
  "type": "FeatureCollection",
  "metadata": {"name": "Demo", "customer": "Acme Co"},
  "features": [ ... ]
}
```

`Project.from_geojson` and the web app will use these fields when initialising a
project. Each uploaded feature also receives an `area_m2` property calculated in
square metres.

### Custom Index
By default the toolkit uses **NDVI** and writes a `mean_ndvi` column.
Pass `--index` and `--value-col` to work with other indices (e.g.
`--index evi --value-col mean_evi`).  These defaults can also be placed
in a configuration file loaded by `ConfigManager`.

## CLI Highlights
- `prepare <input_dir>` – convert shapefiles/KML/KMZ into a clean
  GeoJSON.
- `download timeseries` – fetch spectral index values for each polygon.
- `download chips` – export yearly or monthly imagery chips.
- `download landcover` – export 10 m land-cover rasters.
- `preprocess fill-gaps` – interpolate missing values in a CSV.
- `stats aggregate` – resample daily data to monthly or yearly.
- `stats decompose` – seasonal decomposition with optional plots.
- `stats trend` – compute a linear trend per polygon.
- `visualize plot` – create interactive or static time‑series plots.
- `visualize animate` – build GIF animations from chip folders.
- `gallery` – generate a simple HTML gallery of images.
- `report` – assemble a one‑page HTML summary from all outputs.
- `validate occurrence-density` – compute citizen-science record density for AOIs.
  Example: `verdesat validate occurrence-density aoi.geojson -s 2015 -o dens.csv`.
- `pipeline report` – run the whole NDVI → report workflow in one go.

Run `verdesat --help` for the full set of options.

## 📁 Repository Layout
```
verdesat/
├── core/            # CLI entry points, config & logging
├── ingestion/       # Earth Engine downloader and helpers
├── analytics/       # Time-series utilities and stats
├── visualization/   # Plotting, chip export, report builder
├── services/        # Thin service wrappers for the CLI
├── geo/             # AOI utilities
├── project/         # Project & AOI management
├── resources/       # Sensor specs and index formulas
├── templates/       # Jinja templates for reports
├── modeling/        # (stubs) forecasting models
├── biodiversity/    # (stubs) biodiversity analytics
├── carbon_flux/     # (stubs) carbon flux helpers
└── webapp/          # (stubs) future dashboard code
```
Other top‑level directories include `tests/`, `docs/` and the standard
`Dockerfile` and `pyproject.toml`.

See `docs/development_principles.md` for coding guidelines and
`docs/roadmap.md` for open tasks.

## Dependencies
Core packages include `earthengine-api`, `geopandas`, `pandas` and
`matplotlib`.  Development dependencies are pinned in
`pyproject.toml`.

---
*Designed with ❤️ for a greener planet.*
