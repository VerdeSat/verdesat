"""Helpers to generate simple report figures."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib_map_utils.core.north_arrow import NorthArrow, north_arrow
import numpy as np
import pandas as pd

from verdesat.core.logger import Logger
from verdesat.schemas.reporting import AoiContext

try:  # pragma: no cover - optional dependency
    import contextily as ctx  # type: ignore
except Exception:  # pragma: no cover - contextily missing
    ctx = None


def make_map_png(aoi_ctx: AoiContext, layers: Iterable[str] | None = None) -> bytes:
    """Render an AOI map with basemap and decorations.

    A GeoJSON geometry is plotted when ``aoi_ctx.geometry_path`` points to an
    existing file. The function adds an optional basemap, a scale bar, legend
    and north arrow. If the geometry cannot be read a placeholder image is
    returned instead.

    Parameters
    ----------
    aoi_ctx:
        AOI metadata containing an optional ``geometry_path``.
    layers:
        Optional iterable of layer identifiers (currently unused).
    """

    logger = Logger.get_logger(__name__)
    fig, ax = plt.subplots(figsize=(4, 3))
    geom_path = aoi_ctx.geometry_path

    if geom_path and Path(geom_path).exists():
        gdf = gpd.read_file(geom_path)
        if "id" in gdf.columns:
            gdf = gdf[gdf["id"].astype(str) == str(aoi_ctx.aoi_id)]
        if not gdf.empty:
            gdf = gdf.to_crs(epsg=3857)
            gdf.plot(ax=ax, edgecolor="red", facecolor="none", linewidth=2, label="AOI")
            ax.set_aspect("equal")
            if ctx is not None:
                try:  # pragma: no cover - contextily network usage
                    ctx.add_basemap(ax, source=ctx.providers.CartoDB.PositronNoLabels)
                    ctx.add_basemap(ax, source=ctx.providers.CartoDB.PositronOnlyLabels)
                except Exception:  # pragma: no cover - tile fetch failed
                    logger.warning("Failed to add basemap", exc_info=True)
            _add_scale_bar(ax)
            NorthArrow.set_size("small")
            north_arrow(
                ax,
                location="upper right",
                rotation={"crs": gdf.crs, "reference": "center"},
            )
            ax.legend(loc="lower right")
        else:
            logger.warning("Geometry filtered by id yielded no features")
            ax.text(0.5, 0.5, "map", ha="center", va="center")
            ax.set_axis_off()
    else:  # pragma: no cover - placeholder path
        logger.warning("Geometry path missing for map rendering")
        ax.text(0.5, 0.5, "map", ha="center", va="center")
        ax.set_axis_off()

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _add_scale_bar(ax: plt.Axes) -> None:
    """Draw a simple scale bar in the lower left corner."""

    minx, maxx = ax.get_xlim()
    miny, maxy = ax.get_ylim()
    width = maxx - minx
    # choose a nice rounded length: 1, 2 or 5 * 10^n
    raw_length = width / 5
    magnitude = 10 ** int(np.log10(raw_length))
    norm = raw_length / magnitude
    if norm < 2:
        length = 1 * magnitude
    elif norm < 5:
        length = 2 * magnitude
    else:
        length = 5 * magnitude

    bar_x = minx + width * 0.05
    bar_y = miny + (maxy - miny) * 0.05
    ax.plot([bar_x, bar_x + length], [bar_y, bar_y], color="black", linewidth=2)
    label = f"{int(length/1000)} km" if length >= 1000 else f"{int(length)} m"
    ax.text(
        bar_x + length / 2,
        bar_y + width * 0.01,
        label,
        ha="center",
        va="bottom",
        fontsize=8,
    )


def _add_north_arrow(ax: plt.Axes) -> None:
    """Add a simple north arrow to the map."""

    ax.annotate(
        "N",
        xy=(0.95, 0.05),
        xytext=(0.95, 0.25),
        arrowprops=dict(facecolor="black", width=2, headwidth=8),
        ha="center",
        va="center",
        fontsize=8,
        xycoords="axes fraction",
    )


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
