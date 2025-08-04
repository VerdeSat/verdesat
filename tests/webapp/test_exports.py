import pandas as pd
from shapely.geometry import Polygon

from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
from verdesat.webapp.services import exports


def test_export_project_pdf(monkeypatch):
    metrics = pd.DataFrame({"bscore": [0.5]})
    aoi1 = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    aoi2 = AOI(Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]), {"id": 2})
    project = Project("Demo", "VerdeSat", [aoi1, aoi2], ConfigManager())

    uploaded: dict[str, tuple[str, bytes, str]] = {}

    def fake_upload(key: str, data: bytes, *, content_type: str = "") -> None:
        uploaded["args"] = (key, data, content_type)

    def fake_signed_url(key: str) -> str:
        return f"https://example.com/{key}"

    ndvi_df1 = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "trend": [0.1, 0.2, 0.3],
        }
    )
    ndvi_df2 = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "trend": [0.2, 0.3, 0.4],
        }
    )
    msavi_df = pd.DataFrame(
        {
            "date": list(pd.date_range("2020-01-01", periods=3)) * 2,
            "mean_msavi": [0.1, 0.2, 0.3, 0.2, 0.3, 0.4],
            "id": [1, 1, 1, 2, 2, 2],
        }
    )

    def fake_ndvi(aoi_id: int) -> pd.DataFrame:
        return ndvi_df1 if aoi_id == 1 else ndvi_df2

    monkeypatch.setattr(
        "verdesat.webapp.components.charts.load_ndvi_decomposition", fake_ndvi
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

    proj_msavi = exports._project_msavi_df(project)
    assert set(proj_msavi["id"]) == {1, 2}
    proj_ndvi = exports._project_ndvi_df(project)
    assert set(proj_ndvi["id"]) == {1, 2}
