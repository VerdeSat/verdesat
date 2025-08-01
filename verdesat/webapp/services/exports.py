from __future__ import annotations

"""Utilities for exporting dashboard metrics as files on R2."""

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, cast
from uuid import uuid4

import pandas as pd
import re

from .r2 import upload_bytes, signed_url


def _to_dict(metrics: Mapping[str, float] | object) -> dict[str, float]:
    """Return a plain dict from a metrics container."""

    if is_dataclass(metrics) and not isinstance(metrics, type):
        return {k: float(v) for k, v in asdict(cast(Any, metrics)).items()}
    if isinstance(metrics, Mapping):
        return {k: float(v) for k, v in metrics.items()}
    raise TypeError("metrics must be a dataclass or mapping")


def export_metrics_csv(metrics: Mapping[str, float] | object) -> str:
    """Serialize *metrics* to CSV, upload to R2 and return a signed URL."""

    data = _to_dict(metrics)
    df = pd.DataFrame([data])
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    key = f"results/metrics_{uuid4().hex}.csv"
    upload_bytes(key, csv_bytes, content_type="text/csv")
    return signed_url(key)


def _metrics_html(metrics: Mapping[str, float] | object) -> str:
    data = _to_dict(metrics)
    rows = "".join(f"<tr><th>{k}</th><td>{v:.4f}</td></tr>" for k, v in data.items())
    return f"<h1>VerdeSat Metrics</h1><table>{rows}</table>"


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


def export_metrics_pdf(metrics: Mapping[str, float] | object) -> str:
    """Render *metrics* as a PDF, upload to R2 and return a signed URL."""

    html = _metrics_html(metrics)
    pdf_bytes = _html_to_pdf(html)
    key = f"results/metrics_{uuid4().hex}.pdf"
    upload_bytes(key, pdf_bytes, content_type="application/pdf")
    return signed_url(key)
