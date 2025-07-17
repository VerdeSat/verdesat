import os
from pathlib import Path
from shapely.geometry import Polygon
import pandas as pd
from types import SimpleNamespace

from verdesat.core.pipeline import ReportPipeline
from verdesat.geo.aoi import AOI
from verdesat.ingestion.base import BaseDataIngestor
from verdesat.visualization.visualizer import Visualizer


class DummyIngestor(BaseDataIngestor):
    def __init__(self):
        super().__init__(sensor=SimpleNamespace(collection_id="test/collection"))
        self.timeseries_calls = []
        self.chip_calls = []

    def download_timeseries(
        self,
        aoi: AOI,
        start_date: str,
        end_date: str,
        scale: int,
        index: str,
        chunk_freq: str = "YE",
        freq: str | None = None,
    ) -> pd.DataFrame:
        self.timeseries_calls.append((aoi, start_date, end_date))
        return pd.DataFrame(
            {"id": [aoi.static_props["id"]], "date": [start_date], "mean_ndvi": [0.5]}
        )

    def download_chips(self, aois, config) -> None:  # pragma: no cover - simple stub
        self.chip_calls.append((len(aois), config.out_dir))


class DummyViz(Visualizer):
    def __init__(self):
        super().__init__()
        self.report_called = False

    def plot_decomposition(self, result, output_path: str) -> None:
        Path(output_path).touch()

    def make_gifs_per_site(
        self, images_dir, pattern, output_dir, duration=2, loop=0
    ) -> None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def plot_timeseries_html(self, df, index_col, output_path, agg_freq=None) -> None:
        Path(output_path).write_text("html")

    def generate_report(self, output_dir: str, title: str, map_png=None) -> str:
        self.report_called = True
        path = Path(output_dir, "report.html")
        path.write_text("report")
        return str(path)


def test_report_pipeline_run(tmp_path):
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    ingestor = DummyIngestor()
    viz = DummyViz()

    pipeline = ReportPipeline([aoi], ingestor, viz)
    report_path = pipeline.run(
        start="2020-01-01",
        end="2020-01-31",
        out_dir=str(tmp_path),
    )

    assert os.path.exists(report_path)
    assert ingestor.timeseries_calls
    assert viz.report_called
