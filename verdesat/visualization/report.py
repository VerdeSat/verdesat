import os, json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader
from verdesat.analytics.stats import compute_summary_stats
from verdesat.visualization._collect import collect_assets


def build_report(
    geojson_path: str,
    timeseries_csv: str,
    timeseries_html: Optional[str] = None,
    gifs_dir: Optional[str] = None,
    decomposition_dir: Optional[str] = None,
    chips_dir: Optional[str] = None,
    map_png: Optional[str] = None,
    output_path: str = "verdesat_report.html",
    title: str = "VerdeSat Report",
):

    # 1. Load data
    with open(geojson_path) as f:
        gj = json.load(f)
    run_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    # 2. compute summary stats
    stats_table = compute_summary_stats(timeseries_csv, decomp_dir=decomposition_dir)
    # 3. Discover decomposition images: files named like "1_decomposition.png"
    decomp_pattern = r"(?P<id>\d+)_decomposition\.png"
    decomp_images = {}
    if decomposition_dir:
        decomp_images = collect_assets(
            base_dir=decomposition_dir,
            filename_regex=decomp_pattern,
            key_fn=lambda m: int(m.group("id")),
            date_fn=lambda m: "decomposition",
        )

    # 4. Discover chips gallery: files like "NDVI_<id>_<YYYY-MM-DD>.png"
    gallery_pattern = r"^[^_]+_(?P<id>\d+)_(?P<date>\d{4}-\d{2}-\d{2})\.png$"
    gallery = {}
    if chips_dir:
        gallery = collect_assets(
            base_dir=chips_dir,
            filename_regex=gallery_pattern,
            key_fn=lambda m: int(m.group("id")),
        )
    # Collect GIFs if provided
    gifs = {}
    if gifs_dir:
        gif_pattern = r"(?P<id>\d+)_.*\.gif"
        gifs = collect_assets(
            base_dir=gifs_dir,
            filename_regex=gif_pattern,
            key_fn=lambda m: int(m.group("id")),
            date_fn=lambda m: m.group(0),
        )
    # Load single interactive time-series plot (if provided)
    timeseries_html_div = None
    if timeseries_html:
        from pathlib import Path

        timeseries_html_div = Path(timeseries_html).read_text()
    # 6. Render Jinja
    env = Environment(
        loader=FileSystemLoader(searchpath=Path(__file__).parent.parent / "templates")
    )
    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(
        title=title,
        run_date=run_date,
        stats=stats_table,
        map_png=map_png,
        timeseries_html=timeseries_html_div,
        decomp=decomp_images,
        gallery=gallery,
        gifs=gifs,
    )
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
