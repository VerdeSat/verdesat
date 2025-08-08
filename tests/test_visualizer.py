from __future__ import annotations
from __future__ import annotations

import pandas as pd
from PIL import Image

from verdesat.visualization.visualizer import Visualizer


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 1],
            "date": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "ndvi": [0.1, 0.2],
        }
    )


def test_plot_time_series_creates_png(tmp_path):
    df = _sample_df()
    out = tmp_path / "ts.png"
    viz = Visualizer()
    viz.plot_time_series(df, "ndvi", str(out), agg_freq="ME")
    assert out.exists()


def test_make_gif_builds_animation(tmp_path):
    # create dummy images
    img_dir = tmp_path / "imgs"
    img_dir.mkdir()
    for i, date in enumerate(["20200101", "20200201"], start=1):
        Image.new("RGB", (10, 10)).save(img_dir / f"chip_{date}.png")
    out = tmp_path / "anim.gif"
    viz = Visualizer()
    viz.make_gif(img_dir, "*.png", str(out), duration=0.1)
    assert out.exists()


def test_collect_gallery_groups_images(tmp_path):
    samples = [(1, "2020-01-01"), (1, "2020-01-02"), (2, "2020-01-03")]
    for pid, date in samples:
        Image.new("RGB", (10, 10)).save(tmp_path / f"{pid}_{date}.png")
    viz = Visualizer()
    gallery = viz.collect_gallery(str(tmp_path))
    assert set(gallery.keys()) == {1, 2}
    assert len(gallery[1]) == 2
