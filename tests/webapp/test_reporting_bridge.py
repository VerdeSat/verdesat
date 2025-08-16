import pandas as pd
from shapely.geometry import Polygon
from typing import Any

from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
from verdesat.services.reporting import PackResult
from verdesat.webapp.services.reporting_bridge import build_evidence_pack


def test_build_evidence_pack(monkeypatch):
    aoi = AOI(
        geometry=Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
        static_props={"id": "1", "area_m2": 10_000},
    )
    project = Project(name="Demo", customer="X", aois=[aoi], config=ConfigManager())

    metrics_df = pd.DataFrame(
        [{"id": "1", "ndvi_mean": 0.2, "bscore": 50.0, "bscore_band": "moderate"}]
    )
    ndvi_df = pd.DataFrame(
        {
            "id": ["1"],
            "date": pd.to_datetime(["2024-01-01"]),
            "observed": [0.2],
            "trend": [0.1],
            "seasonal": [0.0],
        }
    )
    msavi_df = pd.DataFrame(
        {"id": ["1"], "date": pd.to_datetime(["2024-01-01"]), "mean_msavi": [0.3]}
    )

    captured: dict[str, Any] = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return PackResult(
            uri="u", url="http://example.com", sha256="0" * 64, bytesize=1
        )

    monkeypatch.setattr(
        "verdesat.webapp.services.reporting_bridge.build_aoi_evidence_pack",
        fake_build,
    )

    result = build_evidence_pack(
        metrics_df,
        ndvi_df,
        msavi_df,
        project,
        "1",
        include_ai=True,
        ai_service="svc",
        ai_request={"x": 1},
    )

    assert isinstance(result, PackResult)
    assert captured["aoi"].aoi_id == "1"
    assert captured["aoi"].geometry_path is not None
    assert set(captured["ts_long"]["var"]) == {"ndvi", "msavi"}
    assert captured["include_ai"] is True
    assert captured["ai_service"] == "svc"
    assert captured["ai_request"] == {"x": 1}


def test_build_evidence_pack_defaults(monkeypatch):
    """Include AI with no service/request uses safe defaults."""

    aoi = AOI(
        geometry=Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
        static_props={"id": "1", "area_m2": 10_000},
    )
    project = Project(name="Demo", customer="X", aois=[aoi], config=ConfigManager())

    metrics_df = pd.DataFrame(
        [{"id": "1", "ndvi_mean": 0.2, "bscore": 50.0, "bscore_band": "moderate"}]
    )
    ndvi_df = pd.DataFrame(
        {
            "id": ["1"],
            "date": pd.to_datetime(["2024-01-01"]),
            "observed": [0.2],
            "trend": [0.1],
            "seasonal": [0.0],
        }
    )
    msavi_df = pd.DataFrame(
        {"id": ["1"], "date": pd.to_datetime(["2024-01-01"]), "mean_msavi": [0.3]}
    )

    captured: dict[str, Any] = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return PackResult(uri="u", url=None, sha256="0" * 64, bytesize=1)

    monkeypatch.setattr(
        "verdesat.webapp.services.reporting_bridge.build_aoi_evidence_pack",
        fake_build,
    )

    build_evidence_pack(
        metrics_df,
        ndvi_df,
        msavi_df,
        project,
        "1",
        include_ai=True,
    )

    assert captured["include_ai"] is True
    assert captured["ai_service"] is not None
    assert captured["ai_request"] == {"aoi_id": "1"}
