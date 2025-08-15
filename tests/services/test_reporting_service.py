import os
import zipfile

import pandas as pd

from verdesat.core.storage import LocalFS
from verdesat.schemas.reporting import AoiContext, MetricsRow, ProjectContext
from verdesat.services.reporting import build_aoi_evidence_pack


class TmpStorage(LocalFS):
    """LocalFS storage rooted at a temporary directory."""

    def __init__(self, base: str) -> None:
        self.base = base

    def join(self, *parts: str) -> str:  # pragma: no cover - trivial
        return os.path.join(self.base, *parts)


def _sample_ts(aoi_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "var": ["ndvi", "ndvi", "ndvi"],
            "stat": ["raw", "raw", "raw"],
            "value": [0.1, 0.2, 0.3],
            "aoi_id": [aoi_id, aoi_id, aoi_id],
            "freq": ["monthly", "monthly", "monthly"],
            "source": ["S2", "S2", "S2"],
        }
    )


def test_build_aoi_evidence_pack(tmp_path) -> None:
    storage = TmpStorage(tmp_path)
    project = ProjectContext(project_id="p1", project_name="Demo")
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"id":"a1"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}}]}'
    )
    aoi = AoiContext(aoi_id="a1", aoi_name="AOI 1", geometry_path=str(geojson))
    metrics = MetricsRow(ndvi_mean=0.2, bscore=42.0, bscore_band="moderate")
    ts_long = _sample_ts(aoi.aoi_id)
    lineage = {"method_version": "0.2.0"}

    result = build_aoi_evidence_pack(
        aoi=aoi,
        project=project,
        metrics=metrics,
        ts_long=ts_long,
        lineage=lineage,
        storage=storage,
    )

    assert result.uri.endswith("a1_evidence_pack.zip")
    assert result.url and result.url.startswith("file://")
    assert len(result.sha256) == 64
    assert result.bytesize > 0

    assert os.path.exists(result.uri)
    with zipfile.ZipFile(result.uri) as zf:
        names = set(zf.namelist())
        assert {
            "report.pdf",
            "metrics.csv",
            "lineage.json",
            "figures/map.png",
            "figures/timeseries.png",
        } <= names
        with zf.open("report.pdf") as fh:
            assert fh.read(4) == b"%PDF"
        with zf.open("metrics.csv") as fh:
            text = fh.read().decode("utf-8")
            assert "ndvi_mean" in text
        with zf.open("figures/map.png") as fh:
            assert fh.read(8).startswith(b"\x89PNG")
