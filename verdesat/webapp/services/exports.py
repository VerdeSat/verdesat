from __future__ import annotations

"""Utilities for exporting dashboard metrics as files on R2."""

from dataclasses import asdict, is_dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, cast
from uuid import uuid4

import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
from verdesat.visualization.visualizer import Visualizer

from .r2 import upload_bytes, signed_url


def _to_dict(metrics: Mapping[str, Any] | object) -> dict[str, Any]:
    """Return a plain ``dict`` from ``metrics`` preserving non-numeric values."""

    def _convert(value: Any) -> Any:
        return float(value) if isinstance(value, (int, float)) else value

    if is_dataclass(metrics) and not isinstance(metrics, type):
        return {k: _convert(v) for k, v in asdict(cast(Any, metrics)).items()}
    if isinstance(metrics, Mapping):
        return {k: _convert(v) for k, v in metrics.items()}
    raise TypeError("metrics must be a dataclass or mapping")


def export_metrics_csv(metrics: Mapping[str, Any] | object, aoi: AOI) -> str:
    """Serialize ``metrics`` for ``aoi`` to CSV and return a presigned URL."""

    data = _to_dict(metrics)
    aoi_id = int(aoi.static_props.get("id", 0))
    data["aoi_id"] = float(aoi_id)
    df = pd.DataFrame([data])
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    key = f"results/aoi_{aoi_id}/metrics_{uuid4().hex}.csv"
    upload_bytes(key, csv_bytes, content_type="text/csv")
    return signed_url(key)


def export_project_csv(metrics: pd.DataFrame, project: Project) -> str:
    """Export aggregated ``metrics`` for ``project`` and return a URL."""

    csv_bytes = metrics.to_csv(index=False).encode("utf-8")
    key = f"results/project_{uuid4().hex}/metrics.csv"
    upload_bytes(key, csv_bytes, content_type="text/csv")
    return signed_url(key)


def export_project_pdf(metrics: pd.DataFrame, project: Project) -> str:
    """Render ``metrics`` for ``project`` as a PDF table and return a URL."""

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    title = getattr(project, "name", "VerdeSat Project")
    c.setTitle(f"{title} Metrics")
    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, title)
    y -= 30

    # Prepare table data
    table_data: list[list[str]] = [list(metrics.columns)]
    for row in metrics.itertuples(index=False):
        formatted = [f"{v:.4f}" if isinstance(v, (int, float)) else str(v) for v in row]
        table_data.append(formatted)

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )

    table_width, table_height = table.wrap(width - 80, height)
    table.drawOn(c, 40, max(40, y - table_height))
    c.save()
    pdf_bytes = buf.getvalue()
    key = f"results/project_{uuid4().hex}/metrics.pdf"
    upload_bytes(key, pdf_bytes, content_type="application/pdf")
    return signed_url(key)


def _aoi_map_png(aoi: AOI) -> bytes:
    """Return a simple PNG rendering of ``aoi`` geometry."""

    import geopandas as gpd  # noqa: WPS433
    import matplotlib.pyplot as plt

    gdf = gpd.GeoDataFrame([{"geometry": aoi.geometry}], crs="EPSG:4326")
    fig, ax = plt.subplots(figsize=(6, 4))
    gdf.plot(ax=ax, edgecolor="#159466", facecolor="none", linewidth=2)
    ax.set_axis_off()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _ndvi_png(aoi_id: int | None, df: pd.DataFrame | None) -> bytes:
    """Generate NDVI decomposition plot using ``Visualizer``."""

    if df is None:
        from verdesat.webapp.components.charts import load_ndvi_decomposition

        if aoi_id is None:
            raise ValueError("aoi_id or df must be provided")
        df = load_ndvi_decomposition(aoi_id)

    class _Decomp:
        def __init__(self, frame: pd.DataFrame):
            self.frame = frame

        def plot(self):  # pragma: no cover - thin wrapper around matplotlib
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(3, 1, sharex=True, figsize=(6, 4))
            axes[0].plot(self.frame["date"], self.frame["observed"])
            axes[0].set_ylabel("Observed")
            axes[1].plot(self.frame["date"], self.frame["trend"])
            axes[1].set_ylabel("Trend")
            axes[2].plot(self.frame["date"], self.frame["seasonal"])
            axes[2].set_ylabel("Seasonal")
            fig.tight_layout()
            return fig

    viz = Visualizer()
    with NamedTemporaryFile(suffix=".png") as tmp:
        viz.plot_decomposition(_Decomp(df), tmp.name)
        return Path(tmp.name).read_bytes()


def _msavi_png(aoi_id: int | None, df: pd.DataFrame | None) -> bytes:
    """Generate MSAVI annual time-series plot."""

    if df is None:
        from verdesat.webapp.components.charts import load_msavi_timeseries

        if aoi_id is None:
            raise ValueError("aoi_id or df must be provided")
        df = load_msavi_timeseries()
        if "id" in df.columns:
            df = df[df["id"] == aoi_id]
    value_col = next(
        (c for c in ("mean_msavi", "msavi") if c in df.columns), df.columns[2]
    )
    viz = Visualizer()
    with NamedTemporaryFile(suffix=".png") as tmp:
        viz.plot_time_series(
            df, index_col=value_col, output_path=tmp.name, agg_freq="YE"
        )
        return Path(tmp.name).read_bytes()


def _build_pdf(
    metrics: Mapping[str, Any],
    aoi: AOI,
    project: str,
    map_png: bytes,
    ndvi_png: bytes,
    msavi_png: bytes,
) -> bytes:
    """Assemble a simple PDF document from supplied assets."""

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    aoi_id = int(aoi.static_props.get("id", 0))

    # Cover page with map and metrics
    c.setTitle(f"{project} AOI {aoi_id} Metrics")
    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, project)
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"AOI {aoi_id}")
    y -= 20
    c.drawImage(
        ImageReader(io.BytesIO(map_png)),
        40,
        y - 180,
        width - 80,
        180,
        preserveAspectRatio=True,
        mask="auto",
    )
    y -= 200
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Metrics")
    y -= 14
    c.setFont("Helvetica", 10)
    for key, val in sorted(metrics.items()):
        if isinstance(val, (int, float)):
            c.drawString(50, y, f"{key}: {val:.4f}")
        else:
            c.drawString(50, y, f"{key}: {val}")
        y -= 12

    # Charts page
    c.showPage()
    c.drawImage(
        ImageReader(io.BytesIO(ndvi_png)),
        40,
        height - 260,
        width - 80,
        240,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.drawImage(
        ImageReader(io.BytesIO(msavi_png)),
        40,
        height - 520,
        width - 80,
        240,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.save()
    return buf.getvalue()


def export_metrics_pdf(
    metrics: Mapping[str, Any] | object,
    aoi: AOI,
    project: str = "VerdeSat Demo",
    ndvi_df: pd.DataFrame | None = None,
    msavi_df: pd.DataFrame | None = None,
) -> str:
    """Render ``metrics`` and visuals for ``aoi`` as a PDF and return a URL."""

    data = _to_dict(metrics)
    map_png = _aoi_map_png(aoi)
    aoi_id = int(aoi.static_props.get("id", 0))
    ndvi_png = _ndvi_png(aoi_id, ndvi_df)
    msavi_png = _msavi_png(aoi_id, msavi_df)
    pdf_bytes = _build_pdf(data, aoi, project, map_png, ndvi_png, msavi_png)
    key = f"results/aoi_{aoi_id}/metrics_{uuid4().hex}.pdf"
    upload_bytes(key, pdf_bytes, content_type="application/pdf")
    return signed_url(key)
