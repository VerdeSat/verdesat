from __future__ import annotations

"""Utilities for exporting dashboard metrics as files on R2."""

from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Mapping, cast
from uuid import uuid4

import base64
import io
import re

import pandas as pd

from .r2 import upload_bytes, signed_url

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    import geopandas as gpd


def _to_dict(metrics: Mapping[str, float] | object) -> dict[str, float]:
    """Return a plain dict from a metrics container."""

    if is_dataclass(metrics) and not isinstance(metrics, type):
        return {k: float(v) for k, v in asdict(cast(Any, metrics)).items()}
    if isinstance(metrics, Mapping):
        return {k: float(v) for k, v in metrics.items()}
    raise TypeError("metrics must be a dataclass or mapping")


def export_metrics_csv(metrics: Mapping[str, float] | object, aoi_id: int) -> str:
    """Serialize *metrics* for ``aoi_id`` to CSV and return a download URL."""

    data = _to_dict(metrics)
    data["aoi_id"] = float(aoi_id)
    df = pd.DataFrame([data])
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    key = f"results/aoi_{aoi_id}/metrics_{uuid4().hex}.csv"
    upload_bytes(key, csv_bytes, content_type="text/csv")
    return signed_url(key)


def _metrics_html(
    metrics: Mapping[str, float] | object,
    aoi_id: int,
    map_b64: str,
    ndvi_b64: str,
    msavi_b64: str,
) -> str:
    data = _to_dict(metrics)
    data["aoi_id"] = float(aoi_id)
    rows = "".join(
        f"<tr><th>{k}</th><td>{v:.4f}</td></tr>" for k, v in sorted(data.items())
    )
    return f"""
    <html>
    <head>
    <style>
        body {{ font-family: sans-serif; }}
        table {{ border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
        h1 {{ color: #159466; }}
    </style>
    </head>
    <body>
        <h1>VerdeSat B-Score Report</h1>
        <h2>AOI {aoi_id}</h2>
        <h3>Project Area Map</h3>
        <img src="data:image/png;base64,{map_b64}" style="max-width:800px;"/>
        <h3>Metrics</h3>
        <table>{rows}</table>
        <h3>NDVI Decomposition</h3>
        <img src="data:image/png;base64,{ndvi_b64}" style="max-width:800px;"/>
        <h3>MSAVI Annual Mean</h3>
        <img src="data:image/png;base64,{msavi_b64}" style="max-width:800px;"/>
    </body>
    </html>
    """


def _html_to_pdf(html: str) -> bytes:
    """Render HTML to PDF using WeasyPrint or pdfkit as fallback."""

    try:
        from weasyprint import HTML  # type: ignore

        return HTML(string=html).write_pdf()
    except Exception:
        try:
            import pdfkit  # type: ignore

            return pdfkit.from_string(html, False)
        except Exception:
            text = re.sub("<[^>]+>", "", html)
            return _basic_pdf(text)


def _basic_pdf(text: str) -> bytes:
    """Return a minimal PDF byte string containing *text*.

    This avoids external dependencies when WeasyPrint and pdfkit are absent.
    The implementation is intentionally simple and not meant for complex
    layouts, but it produces a standards-compliant PDF with the provided text.
    """

    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        f"4 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    header = "%PDF-1.1\n"
    body = ""
    offsets: list[int] = []
    pos = len(header)
    for obj in objects:
        offsets.append(pos)
        body += obj
        pos += len(obj)
    xref_pos = len(header) + len(body)

    xref = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n")
    xref_str = "".join(xref)

    trailer = (
        f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n"
        f"{xref_pos}\n%%EOF"
    )

    return (header + body + xref_str + trailer).encode("latin-1")


def _aoi_map_png(gdf: "gpd.GeoDataFrame") -> bytes:
    """Return a simple PNG rendering of ``gdf`` geometry."""

    import geopandas as gpd  # noqa: WPS433  (import inside function)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    gdf.to_crs("EPSG:4326").plot(
        ax=ax, edgecolor="#159466", facecolor="none", linewidth=2
    )
    ax.set_axis_off()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _ndvi_png(aoi_id: int) -> bytes:
    """Generate NDVI decomposition plot for ``aoi_id`` as PNG."""

    import matplotlib.pyplot as plt
    from verdesat.webapp.components.charts import load_ndvi_decomposition

    df = load_ndvi_decomposition(aoi_id)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(df["date"], df["observed"], label="Observed")
    ax.plot(df["date"], df["trend"], label="Trend")
    ax.plot(df["date"], df["seasonal"], label="Seasonal")
    ax.set_xlabel("Date")
    ax.set_ylabel("NDVI")
    ax.legend()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _msavi_png(aoi_id: int) -> bytes:
    """Generate MSAVI annual bar plot for ``aoi_id`` as PNG."""

    import matplotlib.pyplot as plt
    from verdesat.webapp.components.charts import load_msavi_timeseries

    df = load_msavi_timeseries()
    if "id" in df.columns:
        df = df[df["id"] == aoi_id]
    value_col = next(
        (c for c in ("mean_msavi", "msavi") if c in df.columns), df.columns[2]
    )
    df["year"] = pd.to_datetime(df["date"]).dt.year
    agg = df.groupby("year")[value_col].mean()

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(agg.index.astype(str), agg.values)
    ax.set_xlabel("Year")
    ax.set_ylabel("MSAVI")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def export_metrics_pdf(
    metrics: Mapping[str, float] | object,
    aoi_id: int,
    aoi_gdf: "gpd.GeoDataFrame",
) -> str:
    """Render *metrics* and visuals for ``aoi_id`` as a PDF and return URL."""

    map_b64 = base64.b64encode(_aoi_map_png(aoi_gdf)).decode()
    ndvi_b64 = base64.b64encode(_ndvi_png(aoi_id)).decode()
    msavi_b64 = base64.b64encode(_msavi_png(aoi_id)).decode()
    html = _metrics_html(metrics, aoi_id, map_b64, ndvi_b64, msavi_b64)
    pdf_bytes = _html_to_pdf(html)
    key = f"results/aoi_{aoi_id}/metrics_{uuid4().hex}.pdf"
    upload_bytes(key, pdf_bytes, content_type="application/pdf")
    return signed_url(key)
