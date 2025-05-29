


# VerdeSat Modular Architecture Design

_Last updated: 2025-05-29_

---

## 1. Overview

The VerdeSat MVP is structured to enable scalable, modular, and maintainable geospatial analytics for land monitoring. The architecture is built around clearly defined Python classes and modules, each responsible for a narrow domain, to ensure extensibility and clarity.

---

## 2. High-Level Structure

```
VerdeSatProject
├── AOI [1..N]
│   ├── static_props (dict)
│   ├── geometry (Polygon/MultiPolygon)
│   └── timeseries: {variable: TimeSeries}
│         └── TimeSeries (variable, units, freq, DataFrame)
├── ConfigManager
├── Logger
├── DataIngestor
│   ├── SensorSpec (per backend)
├── AnalyticsEngine
├── Visualizer
└── resources/
```

### Module Mapping

- `core/` — config, logging, cli glue, utils
- `project/` — project and aoi management
- `geo/` — geometric and AOI logic
- `ingestion/` — data download, sensor specs, cloud masking
- `analytics/` — time series, indices, filling, trend, decomposition
- `modeling/` — forecasting models (Prophet, LSTM, etc.)
- `visualization/` — plotting, maps, GIFs, reporting
- `resources/` — palettes, band maps, formulas, etc. (JSON/YAML)

---

## 3. Class & Module Outlines

### core/

#### `ConfigManager`
```python
class ConfigManager:
    """
    Loads and manages configuration from file, env, CLI, or defaults.
    Central entry point for all parameterization.
    """
```

#### `Logger`
```python
class Logger:
    """
    Central logging setup, all modules use this for consistent logging.
    """
```

---

### project/

#### `VerdeSatProject`
```python
class VerdeSatProject:
    """
    Represents a client project. Holds multiple AOIs and project-level metadata.
    Responsible for loading/saving project data and batch operations.
    """
    def __init__(self, name, customer, aois: List['AOI'], config: ConfigManager):
        ...
```

---

### geo/

#### `AOI`
```python
class AOI:
    """
    Area of Interest (AOI): one polygon/multipolygon, with static metadata and time series for each dynamic property.
    """
    def __init__(self, geometry: Polygon or MultiPolygon, static_props: dict, timeseries: Dict[str, TimeSeries] = None):
        self.geometry = geometry
        self.static_props = static_props
        self.timeseries = timeseries or {}

    def add_timeseries(self, variable: str, ts: TimeSeries):
        self.timeseries[variable] = ts
```

---

### analytics/

#### `TimeSeries`
```python
class TimeSeries:
    """
    Holds a time-indexed pandas DataFrame for one variable (e.g., NDVI, precipitation).
    - variable: str
    - units: str
    - freq: str (temporal resolution)
    - df: pd.DataFrame (must have 'date' as index)
    Methods: fill_gaps, decompose, trend, plot, etc.
    """
    def __init__(self, variable, units, freq, df):
        ...
    def fill_gaps(self, method="linear"):
        ...
    def seasonal_decompose(self, period=None):
        ...
```

#### `AnalyticsEngine`
```python
class AnalyticsEngine:
    """
    Collection of static methods for common time series and analytics operations.
    Used by TimeSeries or directly for batch ops.
    """
    @staticmethod
    def compute_trend(ts: 'TimeSeries'):
        ...
```

---

### ingestion/

#### `SensorSpec`
```python
class SensorSpec:
    """
    Contains info about a remote sensing product/collection.
    - bands: Dict[str, str] (e.g., {'nir': 'B8', 'red': 'B4'})
    - native_resolution: int
    - collection_id: str
    - cloud_mask_method: str
    """
    ...
```

#### `DataIngestor`
```python
class DataIngestor:
    """
    Abstract base class for data ingestion. Subclass for EarthEngine, openEO, local, etc.
    """
    def download_timeseries(self, aoi: 'AOI', sensor: 'SensorSpec', index: str, ...):
        raise NotImplementedError()
```

---

### modeling/

#### `ForecastModel` (base class)
```python
class ForecastModel:
    """
    Abstract base for forecasting (Prophet, LSTM, etc).
    """
    def fit(self, timeseries: 'TimeSeries'):
        raise NotImplementedError()
    def predict(self, periods: int):
        raise NotImplementedError()
```

---

### visualization/

#### `Visualizer`
```python
class Visualizer:
    """
    Handles all plotting, static maps, animated GIFs, HTML reports, etc.
    """
    ...
```

---

### resources/

- `palettes.yaml` — Color palettes for indices, customizable.
- `sensor_specs.json` — Sensor/band/collection metadata.
- `index_formulas.json` — List of spectral index formulas, user-extendable.

---

## 4. Critical Config Objects

- `config.toml` or `.env` file for global/project-level parameters (default collection, output dirs, logging level, etc.)
- Sensor/band registry (JSON/YAML)
- Palette and index formula registry (JSON/YAML)
- CLI arguments always override config file/env where applicable

---

## 5. Config & Logging Flow

- **ConfigManager** loads config at program start.
- **Logger** initialized in `core`, used everywhere (no direct `print`).
- All class constructors accept config/logging objects or use defaults.
- Most params (collection, scale, bands, output_dir, etc.) are overrideable from CLI.

---

## 6. OOP Best Practices & Recommendations

- Each class should have a single responsibility.
- Favor composition (AOI contains TimeSeries, not inheritance).
- Use abstract base classes for extensibility (e.g., DataIngestor, ForecastModel).
- Avoid global variables/magic constants — use config/resource files.
- All major classes and public methods must have docstrings.
- Don’t over-engineer — keep it clear and pragmatic for actual analytics.

---

## 7. Roadmap for Next Steps

1. Implement core classes as stubs, then fill in methods during refactor.
2. Move critical logic from scripts into class methods.
3. Parameterize all “critical” hardcoded logic from the audit.
4. Write initial unit tests for each class and method.
5. Document all public interfaces.

---

## 8. Example: Usage Pattern

```python
config = ConfigManager.load("config.toml")
project = VerdeSatProject("ClientXYZ", "Acme Corp", [], config)
aoi = AOI(geometry, {"name": "Field1", "climate_zone": "temperate"})
ts = TimeSeries("ndvi", "unitless", "monthly", df)
aoi.add_timeseries("ndvi", ts)
project.aois.append(aoi)

data_ingestor = EarthEngineIngestor(sensor_spec, config)
data_ingestor.download_timeseries(aoi, sensor_spec, "ndvi", ...)
```

---
# 9. External Solutions Integration

- EODAG: Provides standardized search/download for Sentinel, Landsat, and more. Consider implementing an EODAGDataIngestor to avoid custom download scripts.
- openEO: For future cloud-scale processing, add an OpenEODataIngestor subclass and offer as backend option.
- Index formulas: Move all index calculation formulas to a resource file (JSON/YAML), editable by user. Evaluate [spectral] or other open source registries for expansion.
- Cloud masking: For Sentinel-2, offer s2cloudless as an option. Wrap it as a cloud mask strategy in SensorSpec or DataIngestor.
- Visualization: geemap is recommended for future interactive visualizations in notebooks, but static plotting is prioritized for the CLI MVP.

---
**This architecture supports scalable land/EO analytics, new features, cloud migration, and OOP clarity.**  
Edit and expand as needed!