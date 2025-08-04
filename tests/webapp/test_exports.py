import pandas as pd
from shapely.geometry import Polygon

from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
from verdesat.webapp.services import exports


def test_export_project_pdf(monkeypatch):
    metrics = pd.DataFrame({"id": [1], "bscore": [0.5]})
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    project = Project("Demo", "VerdeSat", [aoi], ConfigManager())

    uploaded: dict[str, tuple[str, bytes, str]] = {}

    def fake_upload(key: str, data: bytes, *, content_type: str = "") -> None:
        uploaded["args"] = (key, data, content_type)

    def fake_signed_url(key: str) -> str:
        return f"https://example.com/{key}"

    ndvi_df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "observed": [0.1, 0.2, 0.3],
            "trend": [0.1, 0.2, 0.3],
            "seasonal": [0.0, 0.0, 0.0],
        }
    )
    msavi_df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "mean_msavi": [0.1, 0.2, 0.3],
            "id": [1, 1, 1],
        }
    )

    monkeypatch.setattr(
        "verdesat.webapp.components.charts.load_ndvi_decomposition",
        lambda aoi_id: ndvi_df,
    )
    monkeypatch.setattr(
        "verdesat.webapp.components.charts.load_msavi_timeseries", lambda: msavi_df
    )
    monkeypatch.setattr(exports, "upload_bytes", fake_upload)
    monkeypatch.setattr(exports, "signed_url", fake_signed_url)

    url = exports.export_project_pdf(metrics, project)

    assert url == f"https://example.com/{uploaded['args'][0]}"
    assert uploaded["args"][2] == "application/pdf"
    assert uploaded["args"][1].startswith(b"%PDF")
