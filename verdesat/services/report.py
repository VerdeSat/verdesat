"""Service layer wrapping report generation utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from verdesat.visualization import report as _report
from verdesat.services.ai_report import AiReportService
from verdesat.schemas.ai_report import AiReportRequest


def build_report(
    *,
    geojson_path: str | None = None,
    timeseries_csv: str | None = None,
    timeseries_html: Optional[str] = None,
    gifs_dir: Optional[str] = None,
    decomposition_dir: Optional[str] = None,
    chips_dir: Optional[str] = None,
    map_png: Optional[str] = None,
    output_path: str = "verdesat_report.html",
    title: str = "VerdeSat Report",
    index_name: str = "ndvi",
    ai_service: AiReportService | None = None,
    ai_request: AiReportRequest | None = None,
) -> str:
    """Generate an HTML report and return the output path.

    When *ai_service* and *ai_request* are supplied, the function renders the
    ``evidence_pack_report.html.j2`` template populated with the AI-generated
    summary blocks. Otherwise it falls back to the legacy visualization report
    renderer.
    """

    if ai_service and ai_request:
        result = ai_service.generate_summary(ai_request)
        summary = result.summary
        kpi = summary.get("kpi_sentences", {})
        esrs = summary.get("esrs_e4", {})
        env = Environment(
            loader=FileSystemLoader(Path(__file__).parent.parent / "templates")
        )
        tmpl = env.get_template("evidence_pack_report.html.j2")
        html = tmpl.render(
            executive_summary=summary.get("executive_summary", ""),
            kpi_sentences=kpi,
            esrs_extent_condition=esrs.get("extent_condition", ""),
            esrs_pressures=esrs.get("pressures", ""),
            esrs_targets=esrs.get("targets", ""),
            esrs_actions=esrs.get("actions", ""),
            esrs_financial_effects=esrs.get("financial_effects", ""),
            report_title=title,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path

    if geojson_path is None or timeseries_csv is None:
        raise ValueError("geojson_path and timeseries_csv are required")

    _report.build_report(
        geojson_path=geojson_path,
        timeseries_csv=timeseries_csv,
        timeseries_html=timeseries_html,
        gifs_dir=gifs_dir,
        decomposition_dir=decomposition_dir,
        chips_dir=chips_dir,
        map_png=map_png,
        output_path=output_path,
        title=title,
        index_name=index_name,
    )
    return output_path
