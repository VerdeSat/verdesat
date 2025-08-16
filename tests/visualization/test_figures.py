import io

import pandas as pd
from PIL import Image

from verdesat.schemas.reporting import AoiContext
from verdesat.visualization import (
    make_map_png,
    make_timeseries_png,
    make_ndvi_trend_png,
    make_yearly_msavi_png,
)


def test_make_map_png_returns_png() -> None:
    data = make_map_png(AoiContext(aoi_id="a1"))
    im = Image.open(io.BytesIO(data))
    assert im.format == "PNG"


def test_make_map_png_with_geojson(tmp_path) -> None:
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"id":1},"geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]}}]}'
    )
    ctx = AoiContext(aoi_id="1", geometry_path=str(geojson))
    data = make_map_png(ctx)
    im = Image.open(io.BytesIO(data))
    assert im.format == "PNG"


def test_make_timeseries_png_returns_png() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-02-01"],
            "var": ["ndvi", "ndvi"],
            "stat": ["raw", "raw"],
            "value": [0.1, 0.2],
            "aoi_id": ["a1", "a1"],
            "freq": ["monthly", "monthly"],
            "source": ["S2", "S2"],
        }
    )
    data = make_timeseries_png(df)
    im = Image.open(io.BytesIO(data))
    assert im.format == "PNG"


def test_ndvi_msavi_plots_return_pngs() -> None:
    df = pd.DataFrame(
        {
            "date": [
                "2024-01-01",
                "2024-02-01",
                "2024-01-01",
                "2024-02-01",
            ],
            "var": ["ndvi", "ndvi", "msavi", "msavi"],
            "stat": ["raw", "raw", "raw", "raw"],
            "value": [0.1, 0.2, 0.3, 0.4],
            "aoi_id": ["a1", "a1", "a1", "a1"],
            "freq": ["monthly", "monthly", "monthly", "monthly"],
            "source": ["S2", "S2", "S2", "S2"],
        }
    )
    ndvi_png = make_ndvi_trend_png(df)
    msavi_png = make_yearly_msavi_png(df)
    assert Image.open(io.BytesIO(ndvi_png)).format == "PNG"
    assert Image.open(io.BytesIO(msavi_png)).format == "PNG"


def test_multi_aoi_plot_handles_duplicate_entries() -> None:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-01"],
            "var": ["ndvi", "ndvi"],
            "stat": ["raw", "raw"],
            "value": [0.1, 0.2],
            "aoi_id": ["a1", "a1"],
            "freq": ["monthly", "monthly"],
            "source": ["S2", "S2"],
        }
    )
    data = make_ndvi_trend_png(df)
    assert Image.open(io.BytesIO(data)).format == "PNG"
