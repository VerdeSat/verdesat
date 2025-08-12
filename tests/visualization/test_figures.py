import io

import pandas as pd
from PIL import Image

from verdesat.schemas.reporting import AoiContext
from verdesat.visualization import make_map_png, make_timeseries_png


def test_make_map_png_returns_png() -> None:
    data = make_map_png(AoiContext(aoi_id="a1"))
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
