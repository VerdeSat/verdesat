from __future__ import annotations

"""Service layer wrapping report generation utilities."""

from typing import Optional

from verdesat.visualization import report as _report


def build_report(
    *,
    geojson_path: str,
    timeseries_csv: str,
    timeseries_html: Optional[str] = None,
    gifs_dir: Optional[str] = None,
    decomposition_dir: Optional[str] = None,
    chips_dir: Optional[str] = None,
    map_png: Optional[str] = None,
    output_path: str = "verdesat_report.html",
    title: str = "VerdeSat Report",
    index_name: str = "ndvi",
) -> str:
    """Generate an HTML report and return the output path."""

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
