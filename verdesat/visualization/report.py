import os, json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from verdesat.analytics.stats import compute_summary_stats
from verdesat.visualization.gallery import collect_gallery


def build_report(
    geojson_path: str,
    timeseries_csv: str,
    decomposition_dir: str,
    chips_dir: str,
    output_path: str,
    title: str = "VerdeSat Report",
):
    # 1. Load data
    with open(geojson_path) as f:
        gj = json.load(f)
    # 2. Compute summary stats (e.g. read CSV, calc slope)
    #    You already have analytics.stats modules—import and use them.
    stats_table = compute_summary_stats(
        timeseries_csv,
        trend_csv=None,  # or pass your trend file (not implemented yet)
        decomp_dir=decomposition_dir,
    )
    # 3. Discover decomposition images
    decomp_images = sorted(Path(decomposition_dir).glob("*.png"))
    # 4. Discover chips gallery
    gallery = collect_gallery(chips_dir)
    # 5. Render Jinja
    env = Environment(
        loader=FileSystemLoader(searchpath=Path(__file__).parent.parent / "templates")
    )
    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(
        title=title,
        stats=stats_table,
        decomp_images=[str(p) for p in decomp_images],
        gallery=gallery,
        # optionally embed map or link to GeoJSON
    )
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
