"""Unified reporting service for generating PDF packs.

This module implements ``build_aoi_evidence_pack`` and
``build_project_pack`` as outlined in ``docs/report_unification.md``.
Reports are rendered using Jinja2 templates and the WeasyPrint PDF
backend. All artefacts are persisted via :class:`~verdesat.core.storage.StorageAdapter`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any
import zipfile

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.schemas.reporting import AoiContext, MetricsRow, ProjectContext, LABELS
from verdesat.visualization import (
    make_map_png,
    make_ndvi_trend_png,
    make_yearly_msavi_png,
)


@dataclass
class PackResult:
    """Metadata about a generated report pack."""

    uri: str
    url: str | None
    sha256: str
    bytesize: int


# ---------------------------------------------------------------------------


def _bytes_to_data_uri(data: bytes, mime: str = "image/png") -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _render_pdf(template: str, context: dict[str, Any]) -> bytes:
    """Render *template* with *context* and return PDF bytes."""

    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    tmpl = env.get_template(template)
    html = tmpl.render(**context)
    pdf = HTML(string=html, base_url=str(templates_dir)).write_pdf()
    return pdf


def _write_pack(
    *,
    pdf_bytes: bytes,
    metrics_csv: bytes,
    lineage: dict,
    map_png: bytes,
    ts_pngs: dict[str, bytes],
    storage: StorageAdapter,
    path_parts: tuple[str, ...],
    ai_summary: dict | None = None,
    aoi_geojson: bytes | None = None,
) -> PackResult:
    """Compose ZIP artefact and persist it using *storage*."""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.pdf", pdf_bytes)
        zf.writestr("metrics.csv", metrics_csv)
        zf.writestr("lineage.json", json.dumps(lineage, indent=2).encode("utf-8"))
        zf.writestr("figures/map.png", map_png)
        for name, png in ts_pngs.items():
            zf.writestr(f"figures/{name}.png", png)
        if ai_summary is not None:
            zf.writestr(
                "ai_summary.json",
                json.dumps(ai_summary, indent=2).encode("utf-8"),
            )
        if aoi_geojson is not None:
            zf.writestr("aoi.geojson", aoi_geojson)

    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    uri = storage.join(*path_parts)
    storage.write_bytes(uri, data)
    try:
        url = storage.presign(uri)
    except Exception:  # pragma: no cover - optional
        url = None
    return PackResult(uri=uri, url=url, sha256=sha, bytesize=len(data))


# ---------------------------------------------------------------------------


def build_aoi_evidence_pack(
    *,
    aoi: AoiContext,
    project: ProjectContext,
    metrics: MetricsRow,
    ts_long: pd.DataFrame,
    lineage: dict,
    include_ai: bool = False,
    storage: StorageAdapter | None = None,
    template: str = "evidence_pack_report.html.j2",
    ai_service: Any | None = None,
    ai_request: Any | None = None,
) -> PackResult:
    """Build an AOI evidence pack and return artefact metadata."""

    storage = storage or LocalFS()
    required = {"date", "var", "stat", "value", "aoi_id", "freq", "source"}
    missing = required - set(ts_long.columns)
    if missing:
        raise ValueError(f"ts_long missing columns: {sorted(missing)}")

    map_png = make_map_png(aoi)
    ndvi_png = make_ndvi_trend_png(ts_long)
    msavi_png = make_yearly_msavi_png(ts_long)
    aoi_geojson: bytes | None = None
    if aoi.geometry_path and Path(aoi.geometry_path).exists():
        aoi_geojson = Path(aoi.geometry_path).read_bytes()

    ai_summary: dict[str, Any] | None = None
    narrative = ""
    if include_ai:
        if not ai_service or not ai_request:
            raise ValueError("ai_service and ai_request required when include_ai=True")
        result = ai_service.generate_summary(ai_request)
        narrative = result.narrative
        ai_summary = result.summary

    def _num(val: Any) -> float:
        return float(val) if val is not None else 0.0

    context: dict[str, Any] = {
        "report_title": "VerdeSat Evidence Pack",
        "report_date": date.today().isoformat(),
        "aoi_name": aoi.aoi_name or "",
        "aoi_id": aoi.aoi_id,
        "method_version": lineage.get("method_version", ""),
        "report_hash": "",
        "bscore": _num(metrics.bscore),
        "bscore_band": (metrics.bscore_band or "").lower(),
        "bscore_band_label": (metrics.bscore_band or "").title(),
        "weights": {"intactness": 0.4, "shannon": 0.3, "fragmentation": 0.3},
        "map_png": _bytes_to_data_uri(map_png),
        "acquisition_from": metrics.window_start or "",
        "acquisition_to": metrics.window_end or "",
        "intactness_pct": _num(metrics.intactness_pct),
        "frag_norm": _num(metrics.frag_norm),
        "msa": _num(metrics.msa),
        "ndvi_mean": _num(metrics.ndvi_mean),
        "ndvi_slope": _num(metrics.ndvi_slope),
        "ndvi_p_value": _num(metrics.ndvi_p_value),
        "ndvi_delta": _num(metrics.ndvi_delta),
        "valid_obs_pct": _num(metrics.valid_obs_pct),
        "executive_summary": narrative,
        "kpi_sentences": {
            "bscore": "",
            "intactness": "",
            "fragmentation": "",
            "ndvi_trend": "",
        },
        "inside_pa": metrics.inside_pa or False,
        "nearest_pa_name": metrics.nearest_pa_name or "",
        "nearest_pa_distance_km": _num(metrics.nearest_pa_distance_km),
        "nearest_kba_name": metrics.nearest_kba_name or "",
        "nearest_kba_distance_km": _num(metrics.nearest_kba_distance_km),
        "ndvi_png": _bytes_to_data_uri(ndvi_png),
        "msavi_png": _bytes_to_data_uri(msavi_png),
        "print_css": (
            Path(__file__).parent.parent / "templates" / "print.css"
        ).read_text(encoding="utf-8"),
        "esrs_extent_condition": "",
        "esrs_pressures": "",
        "esrs_targets": "",
        "esrs_actions": "",
        "esrs_financial_effects": "",
        "methods_text": "",
        "lineage_json": lineage,
        "sources": lineage.get("sources", []),
        "year": date.today().year,
    }

    pdf_bytes = _render_pdf(template, context)
    metrics_csv = pd.DataFrame([asdict(metrics)]).to_csv(index=False).encode("utf-8")

    path = (
        project.project_id,
        aoi.aoi_id,
        f"{aoi.aoi_id}_evidence_pack.zip",
    )
    return _write_pack(
        pdf_bytes=pdf_bytes,
        metrics_csv=metrics_csv,
        lineage=lineage,
        map_png=map_png,
        ts_pngs={"ndvi": ndvi_png, "msavi": msavi_png},
        storage=storage,
        path_parts=path,
        ai_summary=ai_summary,
        aoi_geojson=aoi_geojson,
    )


# ---------------------------------------------------------------------------


def build_project_pack(
    *,
    project: ProjectContext,
    metrics_df: pd.DataFrame,
    ts_long: pd.DataFrame | None,
    lineage: dict,
    storage: StorageAdapter | None = None,
    template: str = "project_pack_report.html.j2",
    aoi: AoiContext | None = None,
) -> PackResult:
    """Build a project-level report pack.

    Parameters
    ----------
    project:
        Project metadata.
    metrics_df:
        Aggregated metrics for the project.
    ts_long:
        Optional long-form timeseries for the project.
    lineage:
        Data lineage metadata.
    storage:
        Storage backend; defaults to :class:`~verdesat.core.storage.LocalFS`.
    template:
        Jinja2 template name.
    aoi:
        Optional :class:`AoiContext` providing a geometry used for the map
        figure. When ``None`` a placeholder map is used.
    """

    metrics_df = metrics_df.copy()
    if "aoi_id" not in metrics_df.columns and "id" in metrics_df.columns:
        metrics_df["aoi_id"] = metrics_df["id"].astype(str)

    storage = storage or LocalFS()
    map_ctx = aoi or AoiContext(aoi_id="")
    map_png = make_map_png(map_ctx)
    ts_long = (
        ts_long
        if ts_long is not None
        else pd.DataFrame(columns=["date", "var", "value", "aoi_id"])
    )
    ndvi_png = make_ndvi_trend_png(ts_long)
    msavi_png = make_yearly_msavi_png(ts_long)

    summary = metrics_df.mean(numeric_only=True).to_dict()

    def _num(val: Any) -> float:
        return float(val) if val is not None and not pd.isna(val) else 0.0

    def _mode(col: str) -> str:
        if col not in metrics_df.columns:
            return ""
        series = metrics_df[col].dropna()
        if series.empty:
            return ""
        return str(series.mode().iat[0])

    inside_pa = (
        bool(metrics_df["inside_pa"].any())
        if "inside_pa" in metrics_df.columns
        else False
    )

    nearest_pa_name = ""
    nearest_pa_distance = 0.0
    if {"nearest_pa_name", "nearest_pa_distance_km"} <= set(metrics_df.columns):
        distances = metrics_df["nearest_pa_distance_km"]
        if not distances.isna().all():
            idx = distances.idxmin()
            nearest_pa_name = str(metrics_df.loc[idx, "nearest_pa_name"])
            nearest_pa_distance = _num(metrics_df.loc[idx, "nearest_pa_distance_km"])

    nearest_kba_name = ""
    nearest_kba_distance = 0.0
    if {"nearest_kba_name", "nearest_kba_distance_km"} <= set(metrics_df.columns):
        distances = metrics_df["nearest_kba_distance_km"]
        if not distances.isna().all():
            idx = distances.idxmin()
            nearest_kba_name = str(metrics_df.loc[idx, "nearest_kba_name"])
            nearest_kba_distance = _num(metrics_df.loc[idx, "nearest_kba_distance_km"])

    biodiv_fields = ["bscore", "intactness_pct", "frag_norm", "shannon", "msa"]
    veg_fields = [
        "ndvi_mean",
        "ndvi_slope",
        "ndvi_delta",
        "ndvi_p_value",
        "msavi_mean",
        "obs_count",
        "valid_obs_pct",
    ]

    def _fmt(val: Any, key: str) -> str:
        if val is None or pd.isna(val):
            return "–"
        if key == "ndvi_p_value":
            return f"{float(val):.3f}"
        if key == "obs_count":
            return str(int(val))
        return f"{float(val):.2f}"

    biodiv_columns = ["AOI"] + [
        LABELS[f] for f in biodiv_fields if f in metrics_df.columns
    ]
    veg_columns = ["AOI"] + [LABELS[f] for f in veg_fields if f in metrics_df.columns]

    biodiv_metrics: list[list[str]] = []
    veg_metrics: list[list[str]] = []
    for _, row in metrics_df.iterrows():
        aoi_label = str(row.get("aoi_name") or row.get("aoi_id"))
        biodiv_metrics.append(
            [aoi_label]
            + [_fmt(row.get(f), f) for f in biodiv_fields if f in metrics_df.columns]
        )
        veg_metrics.append(
            [aoi_label]
            + [_fmt(row.get(f), f) for f in veg_fields if f in metrics_df.columns]
        )

    context = {
        "report_title": "VerdeSat Project Pack",
        "report_date": date.today().isoformat(),
        "project_name": project.project_name,
        "project_id": project.project_id,
        "method_version": lineage.get("method_version", ""),
        "report_hash": "",
        "bscore": _num(summary.get("bscore")),
        "bscore_band": _mode("bscore_band").lower(),
        "bscore_band_label": _mode("bscore_band").title(),
        "weights": {"intactness": 0.4, "shannon": 0.3, "fragmentation": 0.3},
        "map_png": _bytes_to_data_uri(map_png),
        "acquisition_from": (
            metrics_df["window_start"].dropna().min()
            if "window_start" in metrics_df.columns
            else ""
        ),
        "acquisition_to": (
            metrics_df["window_end"].dropna().max()
            if "window_end" in metrics_df.columns
            else ""
        ),
        "intactness_pct": _num(summary.get("intactness_pct")),
        "frag_norm": _num(summary.get("frag_norm")),
        "msa": _num(summary.get("msa")),
        "ndvi_mean": _num(summary.get("ndvi_mean")),
        "ndvi_slope": _num(summary.get("ndvi_slope")),
        "ndvi_p_value": _num(summary.get("ndvi_p_value")),
        "ndvi_delta": _num(summary.get("ndvi_delta")),
        "valid_obs_pct": _num(summary.get("valid_obs_pct")),
        "executive_summary": "",
        "kpi_sentences": {
            "bscore": "",
            "intactness": "",
            "fragmentation": "",
            "ndvi_trend": "",
        },
        "inside_pa": inside_pa,
        "nearest_pa_name": nearest_pa_name,
        "nearest_pa_distance_km": nearest_pa_distance,
        "nearest_kba_name": nearest_kba_name,
        "nearest_kba_distance_km": nearest_kba_distance,
        "ndvi_png": _bytes_to_data_uri(ndvi_png),
        "msavi_png": _bytes_to_data_uri(msavi_png),
        "biodiv_columns": biodiv_columns,
        "biodiv_metrics": biodiv_metrics,
        "veg_columns": veg_columns,
        "veg_metrics": veg_metrics,
        "print_css": (
            Path(__file__).parent.parent / "templates" / "print.css"
        ).read_text(encoding="utf-8"),
        "esrs_extent_condition": "",
        "esrs_pressures": "",
        "esrs_targets": "",
        "esrs_actions": "",
        "esrs_financial_effects": "",
        "methods_text": "",
        "lineage_json": lineage,
        "sources": lineage.get("sources", []),
        "year": date.today().year,
    }

    # Fallback to a tiny inline template if the file is missing.
    try:
        pdf_bytes = _render_pdf(template, context)
    except Exception:
        env = Environment()
        tmpl = env.from_string("<html><body><h1>{{ report_title }}</h1></body></html>")
        html = tmpl.render(**context)
        pdf_bytes = HTML(string=html).write_pdf()

    metrics_csv = metrics_df.to_csv(index=False).encode("utf-8")
    path = (
        project.project_id,
        f"{project.project_id}_project_pack.zip",
    )
    return _write_pack(
        pdf_bytes=pdf_bytes,
        metrics_csv=metrics_csv,
        lineage=lineage,
        map_png=map_png,
        ts_pngs={"ndvi": ndvi_png, "msavi": msavi_png},
        storage=storage,
        path_parts=path,
    )
