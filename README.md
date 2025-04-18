# VerdeSat — Remote Sensing for Sustainability

VerdeSat blends advanced satellite technology with sustainability, focusing on environmental monitoring, biodiversity mapping, and agricultural health. Our minimal, modern toolkit makes it easy to ingest data, run analyses, and build ML models—all in Python.

## 🌱 Brand Essence
- **Mission:** Leverage Earth observation to support sustainable land management and biodiversity conservation.

## 🚀 Quickstart
```bash
# Clone and enter repo
git clone https://github.com/<org>/verdesat.git
cd verdesat

# Install dependencies
pip install -r requirements.txt  # or: poetry install

# Download monthly NDVI composites
verdesat download \
  --geojson path/to/regions.geojson \
  --start 2015-01-01 \
  --end 2024-12-31

# Analyze timeseries
verdesat analyze --datafile output/ndvi_timeseries.csv

# Forecast land-cover change
verdesat forecast
```

## 📁 Repository Structure
```
verdesat/
├── core/              # CLI, config, logging, I/O utils
├── ingestion/         # Satellite + in-situ data ingestion, indices, preprocessing
├── analytics/         # Time-series decomposition, trend analysis, visualization
├── modeling/          # ML pipelines: classification & forecasting
├── agri_health/       # Soil moisture, crop-yield forecasting
├── carbon_flux/       # Eddy-covariance wrappers, carbon-balance calculations
├── webapp/            # Minimal green-themed dashboards (Streamlit/Dash)
├── examples/          # Working demos & notebooks
├── tests/             # Pytest suites (target ≥80% coverage)
├── Dockerfile         # Container definition
├── pyproject.toml     # Project dependencies & metadata
├── requirements.txt   # Pinned dependencies (alternative)
└── README.md          # This file
```

## 🛠  Dependencies
- Core: `earthengine-api`, `geopandas`, `pandas`, `numpy`
- Raster: `rioxarray`, `xarray`, `xarray-spatial`
- Viz & Analysis: `matplotlib`, `plotly`, `statsmodels`, `scikit-learn`
- ML & Modeling: `pytorch` or `tensorflow`, `prophet`, `xgboost`
- Spatial libs: `pyproj`, `shapely>=2.0`, `planetary-computer`, `stac-client`
- Optional: `landlab`, `pysheds`, `fastapi`, `streamlit`

## 🎯 Phase 1 Deliverables
1. Monorepo scaffold + stub modules
2. Locked dependencies (pyproject.toml or requirements.txt)
3. Core CLI (`verdesat download`, `verdesat analyze`, `verdesat forecast`)
4. End-to-end example: monthly NDVI > CSV > decomposition plot

## 🛣️ Phase 2 Roadmap
- **Data**: daily/time-window composites, in-situ CSV ingestion, caching layer
- **Analytics**: interactive dashboards (Dash/Streamlit), advanced trend fits
- **Modeling**: LSTM/Prophet forecasting, hyperparameter tuning (Optuna)
- **Packaging & CI**: pip modules, GitHub Actions for lint/tests, PyPI release
- **Cloud**: Helm charts, Kubernetes jobs, Airflow/Prefect workflows, S3/GCS I/O

## 🔧 Best Practices
- **Type hints & docstrings** (enforce with `mypy`)
- **`pytest`** for unit & integration tests (≥80% coverage)
- **`black` + `flake8`** via pre-commit hooks for style
- **Modular interfaces**: abstract I/O & compute backends
- **Dependency injection** in ML pipelines
- **Semantic versioning** & `CHANGELOG.md`
- **CI/CD**: lint → tests → build → publish
- **Docker + Helm** for reproducible deployments

---
*Designed with ❤️ for a greener planet.*

