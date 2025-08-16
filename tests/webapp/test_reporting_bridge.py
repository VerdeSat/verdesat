import pandas as pd
from pathlib import Path
from shapely.geometry import Polygon

from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
from verdesat.services.reporting import PackResult
from verdesat.webapp.services.reporting_bridge import build_project_pack


def test_build_project_pack(monkeypatch):
    metrics = pd.DataFrame({"id": [1], "ndvi_mean": [0.5]})
    ndvi_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-06-01", "2020-07-01"]),
            "observed": [0.2, 0.3],
            "trend": [0.2, 0.3],
            "seasonal": [0.0, 0.0],
            "id": [1, 1],
        }
    )
    msavi_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-06-01", "2020-07-01"]),
            "mean_msavi": [0.1, 0.2],
            "id": [1, 1],
        }
    )
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    project = Project("Demo", "VerdeSat", [aoi], ConfigManager())

    captured: dict[str, object] = {}

    def fake_service(**kwargs):
        captured.update(kwargs)
        return PackResult(uri="proj.zip", url=None, sha256="x", bytesize=1)

    monkeypatch.setattr(
        "verdesat.webapp.services.reporting_bridge.build_project_pack_service",
        fake_service,
    )

    result = build_project_pack(
        metrics,
        ndvi_df,
        msavi_df,
        project,
        start_year=2020,
        end_year=2020,
    )

    assert result.uri == "proj.zip"
    assert captured["project"].project_id == "Demo"
    assert {"ndvi", "msavi"} == set(captured["ts_long"]["var"].unique())
    assert captured["aoi"].aoi_id == "project"
    assert str(captured["aoi"].geometry_path).endswith(".geojson")
