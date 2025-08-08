from __future__ import annotations

import types
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon


def _load_app_module(monkeypatch):
    """Load app.py up to the Streamlit UI block."""
    src = Path("verdesat/webapp/app.py").read_text(encoding="utf-8")
    prefix = src.split("# ---- Page config")[0]
    module = types.ModuleType("app_partial")
    module.__file__ = "verdesat/webapp/app.py"
    exec(compile(prefix, "verdesat/webapp/app.py", "exec"), module.__dict__)
    return module


def test_load_demo_project_attaches_rasters(monkeypatch, tmp_path):
    app = _load_app_module(monkeypatch)
    gdf = gpd.GeoDataFrame(
        {"id": [1], "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]},
        crs="EPSG:4326",
    )
    geojson_path = tmp_path / "demo.geojson"
    gdf.to_file(geojson_path, driver="GeoJSON")
    monkeypatch.setattr(app, "DEMO_AOI_KEY", str(geojson_path))
    monkeypatch.setattr(
        app, "_demo_cfg", {"aois": [{"id": 1, "ndvi": "n.tif", "msavi": "m.tif"}]}
    )
    monkeypatch.setattr(app, "signed_url", lambda key: key)
    project = app.load_demo_project()
    assert project.rasters["1"]["ndvi"] == "n.tif"
    assert project.rasters["1"]["msavi"] == "m.tif"


def test_compute_project_returns_expected(monkeypatch):
    app = _load_app_module(monkeypatch)

    class DummyBar:
        def __init__(self):
            self.updated = False

        def progress(self, frac, text=""):
            self.updated = True

        def empty(self):
            pass

    bar = DummyBar()
    app.st.progress = lambda value, text="": bar  # type: ignore[attr-defined]

    metrics_df = pd.DataFrame({"id": [1], "bscore": [1.0]})
    ndvi_df = pd.DataFrame(
        {"id": [1], "date": pd.to_datetime(["2020-01-01"]), "observed": [0.1]}
    )
    msavi_df = pd.DataFrame(
        {"id": [1], "date": pd.to_datetime(["2020-01-01"]), "mean_msavi": [0.2]}
    )

    class DummyService:
        def compute(self, project, start, end, progress):
            progress(0.5)
            project.rasters = {"1": {"ndvi": "n", "msavi": "m"}}
            project.metrics = {"1": {"bscore": 1}}
            return metrics_df, ndvi_df, msavi_df

    app.project_compute = DummyService()  # type: ignore[attr-defined]
    dummy_project = types.SimpleNamespace(rasters={}, metrics={})
    result = app.compute_project(dummy_project, 2020, 2020)
    assert bar.updated
    assert result[0].equals(metrics_df)
    assert result[3]["1"] == "n"
    assert result[4]["1"] == "m"
