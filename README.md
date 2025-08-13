![CI](https://github.com/VerdeSat/verdesat/actions/workflows/ci.yml/badge.svg)
# VerdeSat — Remote Sensing for Sustainability

VerdeSat is a modular, cloud-ready geospatial analytics toolkit. It ingests Earth-observation data, computes vegetation and biodiversity metrics, and serves results through a CLI and a Streamlit dashboard. Heavy artifacts live in Cloudflare R2.

---

## 🌱 Mission
Use satellites to support sustainable land management and biodiversity conservation with **transparent, reproducible** analytics.

---

## 🚀 Quickstart

### 1) Install
```bash
# Clone and set up (Poetry recommended)
git clone https://github.com/VerdeSat/verdesat.git
cd verdesat
./setup.sh  # or: poetry install
```

### 2) Run the dashboard
```bash
# Local
poetry run streamlit run verdesat/webapp/app.py
# Or via CLI helper
poetry run verdesat webapp
```
Set the following if you use a **private R2 bucket** for rasters:
```bash
export R2_ENDPOINT=https://<account>.r2.cloudflarestorage.com
export R2_BUCKET=verdesat-data
export R2_KEY=...
export R2_SECRET=...
```

### 3) CLI highlights
```bash
# Prepare vectors → clean GeoJSON
verdesat prepare ./input_dir -o aoi.geojson

# Download spectral index time series
verdesat timeseries aoi.geojson --index ndvi --start 2024-01-01 --end 2024-12-31 -o ndvi.csv

# Export yearly chips / land-cover
verdesat chips aoi.geojson --year 2024 -o chips/
verdesat landcover aoi.geojson --year 2024 -o lc_2024.tif

# Compute biodiversity scores
verdesat bscore-from-geojson aoi.geojson --year 2024 -o metrics.csv

# Build a one-page HTML/PDF report
verdesat report html aoi.geojson ndvi.csv ndvi.html -d decompositions/ -c chips/ -o report.html

# Generate an AI executive summary
verdesat report ai --project P1 --aoi A1 --metrics metrics.csv --timeseries ndvi.csv
```
Run `verdesat --help` for the full set of commands.

### 4) Build an evidence pack with AI summary

```bash
# Start from a GeoJSON AOI
export AOI=aoi.geojson

# 1. Compute project metrics (single-row CSV)
verdesat bscore-from-geojson $AOI --year 2024 -o metrics.csv

# 2. Fetch NDVI time series
verdesat timeseries $AOI --index ndvi --start 2024-01-01 --end 2024-12-31 -o ts.csv

# 3. Record processing lineage (minimal example)
cat > lineage.json <<'EOF'
{ "metrics": "metrics.csv", "timeseries": "ts.csv" }
EOF

# 4. Package everything and let the AI summarise
verdesat pack aoi --aoi-id A1 --metrics metrics.csv --ts ts.csv --lineage lineage.json --include-ai
```
The command emits a ZIP archive (e.g. `A1_evidence_pack.zip`) containing `report.pdf`, data files and figures. Using `--out r2` stores it in Cloudflare R2 and prints a presigned URL.

---

## 📁 Repository layout (short)
```
verdesat/
├── analytics/              # Time-series utilities & stats
├── biodiv/                 # Biodiversity metrics & B-Score
├── core/                   # CLI, config, logging, storage
├── geo/                    # AOI model
├── ingestion/              # Earth Engine ingestor & helpers
├── project/                # Project model
├── services/               # Thin service layer (landcover, msa, report, ...)
├── visualization/          # Chip export, plotting, HTML reports
└── webapp/                 # Streamlit app (components, services, themes)
```
See `docs/MODULES.md` for an auto-generated, detailed list.

---

## 🧱 Architecture (at a glance)
- **MVP:** Streamlit + Python services; R2 presigned URLs; Titiler for tiles.
- **Target v1.0:** FastAPI Core + Postgres/PostGIS + Worker/Queue + R2; CLI & Web consume the API.

Read more in `docs/architecture.md` and the delivery plan in `docs/roadmap.md`.

---

## 🛠 Development
- Follow `docs/development_principles.md` (OOP, DI, 12-factor config, typed public APIs).
- Run tests in CI; prefer unit tests (fast), then integration (EE mocked).
- Use `scripts/inventory.py --write` to refresh `docs/MODULES.md`.

## Dependencies
Core: `earthengine-api`, `geopandas`, `pandas`, `numpy`, `matplotlib`.
Web: `streamlit`, `folium`, `streamlit-folium`.
Storage: `boto3` for R2/S3.
(See `pyproject.toml` for pinned versions.)

---

*Built with ❤️ for a greener planet.*
