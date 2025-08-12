"""Helpers to generate simple report figures."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from verdesat.schemas.reporting import AoiContext


def make_map_png(aoi_ctx: AoiContext, layers: Iterable[str] | None = None) -> bytes:
    """Return a placeholder map image as PNG bytes.

    Parameters
    ----------
    aoi_ctx:
        AOI metadata (unused placeholder).
    layers:
        Optional iterable of layer identifiers.
    """
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.text(0.5, 0.5, "map", ha="center", va="center")
    ax.set_axis_off()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def make_timeseries_png(ts_long: pd.DataFrame) -> bytes:
    """Plot a simple timeseries and return PNG bytes."""
    df = ts_long.copy()
    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="var", values="value")
    pivot.sort_index(inplace=True)
    fig, ax = plt.subplots(figsize=(4, 3))
    pivot.plot(ax=ax)
    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
