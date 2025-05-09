import os, json
from pathlib import Path
from datetime import datetime
from typing import Dict
from jinja2 import Environment, FileSystemLoader
from verdesat.analytics.stats import compute_summary_stats
from verdesat.visualization._collect import collect_assets


def load_timeseries_divs(html_dir: str) -> Dict[str, str]:
    """
    Read all files timeseries_<id>.html in html_dir and return { id: html_div, … }.
    """
    divs = {}
    for p in Path(html_dir).glob("timeseries_*.html"):
        pid = p.stem.split("_")[1]
        divs[pid] = p.read_text()
    return divs


def build_report(
    geojson_path: str,
    timeseries_csv: str,
    decomposition_dir: str,
    chips_dir: str,
    map_png: str = None,
    output_path: str = None,
    title: str = "VerdeSat Report",
):
    # 1. Load data
    with open(geojson_path) as f:
        gj = json.load(f)
    run_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    # 2. Compute summary stats (e.g. read CSV, calc slope)
    stats_table = compute_summary_stats(timeseries_csv, decomposition_dir)
    # 3. Discover decomposition images: files named like "1_decomposition.png"
    decomp_pattern = r"(?P<id>\d+)_decomposition\.png"
    decomp_images = collect_assets(
        base_dir=decomposition_dir,
        filename_regex=decomp_pattern,
        # date_fn can be a no‐op since there's no date in the filename:
        date_fn=lambda m: "decomposition",
    )

    # 4. Discover chips gallery: files like "NDVI_<id>_<YYYY-MM-DD>.png"
    gallery_pattern = r"(?P<id>\d+)_(?P<date>\d{4}-\d{2}-\d{2})\.png"
    gallery = collect_assets(
        base_dir=chips_dir,
        filename_regex=gallery_pattern,
        # key_fn default extracts m.group("id"), date_fn default m.group("date")
    )
    # 5. Load timeseries HTML divs
    timeseries_divs = load_timeseries_divs(timeseries_csv)
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
        timeseries=timeseries_divs,
        decomp=decomp_images,
        gallery=gallery,
    )
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
