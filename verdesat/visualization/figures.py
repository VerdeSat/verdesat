"""Helpers to generate simple report figures."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from verdesat.schemas.reporting import AoiContext


def make_map_png(aoi_ctx: AoiContext, layers: Iterable[str] | None = None) -> bytes:
    """Render a simple AOI map and return PNG bytes.

    If ``aoi_ctx.geometry_path`` points to a GeoJSON file the corresponding
    geometry is plotted. Otherwise a placeholder image is returned.

    Parameters
    ----------
    aoi_ctx:
        AOI metadata containing an optional ``geometry_path``.
    layers:
        Optional iterable of layer identifiers (currently unused).
    """
    fig, ax = plt.subplots(figsize=(4, 3))
    geom_path = aoi_ctx.geometry_path
    if geom_path and Path(geom_path).exists():
        gdf = gpd.read_file(geom_path)
        if "id" in gdf.columns:
            gdf = gdf[gdf["id"] == aoi_ctx.aoi_id]
        gdf.plot(ax=ax, edgecolor="red", facecolor="none")
        ax.set_axis_off()
    else:  # pragma: no cover - placeholder path
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
