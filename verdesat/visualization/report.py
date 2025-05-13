import os, json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader
from verdesat.analytics.stats import compute_summary_stats
from verdesat.visualization._collect import collect_assets
from collections import defaultdict


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

    html_dir = Path(output_path).parent

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

    # 4. Discover chips gallery (annual PNGs)
    gallery = collect_assets(
        base_dir=chips_dir,
        filename_regex=r"NDVI_(?P<id>\d+)_(?P<date>\d{4}-\d{2}-\d{2})\.png$",
        key_fn=lambda m: m.group("id"),
        date_fn=lambda m: m.group("date"),
    )
    # 4.1 Group gallery files by year per site
    gallery_by_year: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for site, items in gallery.items():
        for date, path in items:
            year = date[:4]
            gallery_by_year[site][year].append((date, path))

    # 4.2 Discover and group animated GIFs by year per site
    gifs_base = Path(output_path).parent / "gifs"
    gifs = collect_assets(
        base_dir=str(gifs_base),
        filename_regex=r"(?P<id>\d+)___(?P<year>\d{4})_png\.gif",
        key_fn=lambda m: m.group("id"),
        date_fn=lambda m: m.group("year"),
    )
    gifs_by_year: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for site, items in gifs.items():
        for year, path in items:
            gifs_by_year[site][year].append((year, path))

    # Rebase all asset paths to be relative to the report HTML
    for site, items in decomp_images.items():
        decomp_images[site] = [
            (date, str(Path(path).relative_to(html_dir))) for date, path in items
        ]

    for site, yearly in gallery_by_year.items():
        gallery_by_year[site] = {
            year: [
                (date, str(Path(path).relative_to(html_dir))) for date, path in items
            ]
            for year, items in yearly.items()
        }

    for site, yearly in gifs_by_year.items():
        gifs_by_year[site] = {
            year: [
                (label, str(Path(path).relative_to(html_dir))) for label, path in items
            ]
            for year, items in yearly.items()
        }

    # Load single interactive time-series plot (if provided)
    timeseries_html_div = None
    if timeseries_html:
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
        gallery_by_year=gallery_by_year,
        gifs_by_year=gifs_by_year,
    )
    os.makedirs(Path(output_path).parent, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
