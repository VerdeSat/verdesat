"""
VerdeSat CLI entrypoint — defines commands for vector preprocessing, time series download,
and basic workflows. Dynamically loads available indices from the registry.
"""

import os
import sys
from datetime import datetime

import pandas as pd
import click  # type: ignore
from click import echo
from verdesat.ingestion.vector_preprocessor import VectorPreprocessor
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.ingestion import create_ingestor
from verdesat.ingestion.indices import INDEX_REGISTRY
from verdesat.analytics.timeseries import TimeSeries
from verdesat.visualization.static_viz import plot_decomposition
from verdesat.analytics.decomposition import decompose_each
from verdesat.analytics.trend import compute_trend
from verdesat.analytics.preprocessing import interpolate_gaps
from verdesat.visualization.plotly_viz import plot_timeseries_html
from verdesat.visualization.static_viz import plot_time_series
from verdesat.visualization.gallery import build_gallery
from verdesat.visualization.animate import make_gifs_per_site
from verdesat.ingestion.eemanager import ee_manager
from verdesat.visualization.chips import ChipService
from verdesat.geo.aoi import AOI
from verdesat.visualization._chips_config import ChipsConfig
from verdesat.core.logger import Logger

logger = Logger.get_logger(__name__)


@click.group()
def cli():
    """VerdeSat: remote-sensing analytics toolkit."""
    Logger.setup()


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
def prepare(input_dir):
    """Process all vector files in INPUT_DIR into a single, clean GeoJSON."""
    try:
        vp = VectorPreprocessor(input_dir, logger=logger)
        gdf = vp.run()
        output_path = os.path.join(
            input_dir, f"{os.path.basename(input_dir)}_processed.geojson"
        )
        gdf.to_file(output_path, driver="GeoJSON")
        echo(f"✅  GeoJSON written to `{output_path}`")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        echo(f"❌  Processing failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def forecast():
    """Run forecasting pipelines (Prophet, LSTM, etc.)."""
    echo("Forecasting…")


@cli.group()
def download():
    """Data ingestion commands."""


@download.command(name="timeseries")
@click.argument("geojson", type=click.Path(exists=True))
@click.option(
    "--collection",
    "-c",
    default="NASA/HLS/HLSL30/v002",
    help="Earth Engine ImageCollection ID",
)
@click.option("--start", "-s", default="2015-01-01", help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", default="2024-12-31", help="End date (YYYY-MM-DD)")
@click.option("--scale", type=int, default=30, help="Spatial resolution (meters)")
@click.option(
    "--index",
    "-i",
    type=click.Choice(list(INDEX_REGISTRY.keys())),
    default="ndvi",
    help=f"Spectral index to compute (choices: {', '.join(INDEX_REGISTRY.keys())})",
)
@click.option(
    "--agg",
    "-a",
    type=click.Choice(["D", "ME", "YE"]),
    default=None,
    help="Temporal aggregation: D, ME, YE",
)
@click.option(
    "--chunk_freq",
    "-ch",
    default="YE",
    type=click.Choice(["D", "ME", "YE"]),
    help="Chunk frequency: D, ME, YE",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="timeseries.csv",
    help="Output CSV path",
)
@click.option(
    "--backend",
    "-b",
    default="ee",
    help="Data ingestion backend (e.g. 'ee').",
)
def timeseries(
    geojson, collection, start, end, scale, index, chunk_freq, agg, output, backend
):
    """
    Download and aggregate spectral index timeseries for polygons in GEOJSON.
    """
    try:
        echo(f"Loading AOIs from {geojson}...")
        aois = AOI.from_geojson(geojson, id_col="id")
        sensor = SensorSpec.from_collection_id(collection)
        ingestor = create_ingestor(
            backend,
            sensor,
            ee_manager_instance=ee_manager,
            logger=logger,
        )
        df_list = []
        for aoi in aois:
            df = ingestor.download_timeseries(
                aoi, start, end, scale, index, chunk_freq, agg
            )
            df_list.append(df)
        result = pd.concat(df_list, ignore_index=True)
        echo(f"Saving results to {output}...")
        result.to_csv(output, index=False)
        echo("Done.")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error("Timeseries command failed", exc_info=True)
        echo(f"❌  Timeseries download failed: {e}", err=True)
        sys.exit(1)


@download.command(name="chips")
@click.option(
    "--mask-clouds/--no-mask-clouds",
    default=True,
    help="Apply Fmask‐based cloud/shadow/water masking before composites.",
)
@click.argument("geojson", type=click.Path(exists=True))
@click.option(
    "--collection",
    "-c",
    default="NASA/HLS/HLSL30/v002",
    help="Earth Engine ImageCollection ID.",
)
@click.option("--start", "-s", default="2015-01-01", help="Start date (YYYY-MM-DD).")
@click.option("--end", "-e", default="2024-12-31", help="End date (YYYY-MM-DD).")
@click.option(
    "--period",
    "-p",
    type=click.Choice(["ME", "YE"]),
    default="ME",
    help="Composite period: M=monthly, Y=yearly.",
)
@click.option(
    "--type",
    "-t",
    "chip_type",
    type=str,
    default="red,green,blue",
    help=(
        "Either a comma-separated list of band aliases (e.g. 'red,green,blue') "
        "or the name of any index in INDEX_REGISTRY (e.g. 'ndvi', 'evi')."
    ),
)
@click.option("--scale", type=int, default=30, help="Resolution in meters.")
@click.option(
    "--min-val",
    type=float,
    default=None,
    help="Minimum stretch value (overridden by defaults if not set).",
)
@click.option(
    "--max-val",
    type=float,
    default=None,
    help="Maximum stretch value (overridden by defaults if not set).",
)
@click.option(
    "--buffer",
    type=int,
    default=0,
    help="Buffer distance (meters) to apply around each polygon.",
)
@click.option(
    "--buffer-percent",
    type=float,
    default=None,
    help="Buffer distance as a percentage of AOI size.",
)
@click.option(
    "--gamma",
    type=float,
    default=None,
    help="Gamma correction value (e.g. 0.8).",
)
@click.option(
    "--percentile-low",
    type=float,
    default=None,
    help="Lower percentile for auto-stretch (e.g. 2).",
)
@click.option(
    "--percentile-high",
    type=float,
    default=None,
    help="Upper percentile for auto-stretch (e.g. 98).",
)
@click.option(
    "--palette",
    "palette_arg",
    type=str,
    default=None,
    help=(
        "Optional color palette for INDEX outputs. Either a preset name "
        "(e.g. 'white-green', 'red-white-green') or a comma-separated list "
        "of hex/RGB colors."
    ),
)
@click.option(
    "--format",
    "-f",
    "fmt",
    default="png",
    help="Output file format ('png' or 'geotiff').",
)
@click.option("--out-dir", "-o", default="chips", help="Output directory.")
@click.option(
    "--backend",
    "-b",
    default="ee",
    help="Data ingestion backend (e.g. 'ee').",
)
@click.option(
    "--ee-project",
    "_ee_project",
    default=None,
    help="Override Earth Engine project (GCP).",
)
def chips(
    mask_clouds,
    geojson,
    collection,
    start,
    end,
    period,
    chip_type,
    scale,
    min_val,
    max_val,
    buffer,
    buffer_percent,
    gamma,
    percentile_low,
    percentile_high,
    palette_arg,
    fmt,
    out_dir,
    backend,
    _ee_project,
):
    """
    Download per-polygon image chips (monthly/yearly composites).

    CHIP_TYPE may be:
      • a comma-separated list of sensor band aliases (e.g. 'red,green,blue'), or
      • the name of any index defined in INDEX_REGISTRY (e.g. 'ndvi', 'evi').
    """
    try:
        # 1) Load AOIs (list of AOI objects) from GeoJSON path
        echo(f"Loading AOIs from {geojson}...")
        aois = AOI.from_geojson(geojson, id_col="id")

        # 2) Build a SensorSpec from the chosen collection ID
        sensor_spec = SensorSpec.from_collection_id(collection)

        # 3) Build a ChipsConfig from all CLI options
        chips_cfg = ChipsConfig.from_cli(
            collection=collection,
            start=start,
            end=end,
            period=period,
            chip_type=chip_type,
            scale=scale,
            buffer=buffer,
            buffer_percent=buffer_percent,
            min_val=min_val,
            max_val=max_val,
            gamma=gamma,
            percentile_low=percentile_low,
            percentile_high=percentile_high,
            palette_arg=palette_arg,
            fmt=fmt,
            out_dir=out_dir,
            mask_clouds=mask_clouds,
        )

        echo("→ Building composites and exporting chips…")

        # 4) Instantiate ingestor via factory and run chip export
        ingestor = create_ingestor(
            backend,
            sensor_spec,
            ee_manager_instance=ee_manager,
            logger=logger,
        )
        ingestor.download_chips(aois=aois, config=chips_cfg)

        echo(f"✅  Chips written under {out_dir}/")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error("Chips command failed", exc_info=True)
        echo(f"❌  Chips download failed: {e}", err=True)
        sys.exit(1)


@cli.group()
def stats():
    """Statistical operations on time-series data."""


@stats.command(name="aggregate")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index",
    "-i",
    type=click.Choice(["ndvi", "evi"]),
    default="ndvi",
    help="Spectral index that was computed (e.g., ndvi, evi)",
)
@click.option(
    "--freq",
    "-f",
    type=click.Choice(["D", "ME", "YE"]),
    default="D",
    help="Frequency to aggregate to: D (daily), M (monthly), Y (yearly)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="aggregated.csv",
    help="Output path for the aggregated CSV",
)
def aggregate(input_csv, index, freq, output):
    """
    Aggregate a raw daily time-series CSV to the specified frequency.
    """

    echo(f"Loading {input_csv}...")
    df = pd.read_csv(input_csv, parse_dates=["date"])
    echo(f"Aggregating by frequency '{freq}' for index '{index}'...")
    ts = TimeSeries.from_dataframe(df, index=index)
    df_agg = ts.aggregate(freq).df
    echo(f"Saving aggregated data to {output}...")
    df_agg.to_csv(output, index=False)
    echo("Done.")


@cli.group()
def preprocess():
    """Data transformation commands (gap-fill, resample, etc.)."""


@preprocess.command(name="fill-gaps")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--value-col",
    "-c",
    default="mean_ndvi",
    help="Column to fill gaps in (e.g. mean_ndvi)",
)
@click.option(
    "--method", "-m", default="time", help="Interpolation method (time, linear, etc.)"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="filled.csv",
    help="Output path for gap-filled CSV",
)
def fill_gaps_cmd(input_csv, value_col, method, output):
    """Interpolate missing values in a time-series CSV."""

    echo(f"Loading {input_csv}...")
    df = pd.read_csv(input_csv, parse_dates=["date"])
    echo(f"Filling gaps in '{value_col}', method '{method}'...")
    df_filled = interpolate_gaps(
        df, date_col="date", value_col=value_col, method=method
    )
    echo(f"Saving filled data to {output}...")
    df_filled.to_csv(output, index=False)
    echo("Done.")


@stats.command(name="decompose")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index-col",
    "-c",
    default="mean_ndvi",
    help="Column in CSV for decomposition (e.g. mean_ndvi)",
)
@click.option(
    "--model",
    "-m",
    type=click.Choice(["additive", "multiplicative"]),
    default="additive",
    help="Decomposition model",
)
@click.option(
    "--period", "-p", type=int, default=12, help="Seasonal period (e.g. 12 for monthly)"
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="decomposition",
    help="Directory to save outputs",
)
@click.option(
    "--plot/--no-plot",
    default=True,
    help="Whether to generate PNG plots for each polygon (default: True)",
)
def decompose(input_csv, index_col, model, period, output_dir, plot):
    """
    Perform seasonal decomposition on a pivoted CSV and save plot.
    """
    echo(f"Loading {input_csv}...")
    df = pd.read_csv(input_csv, parse_dates=["date"])
    df_pivot = df.set_index("date").pivot(columns="id", values=index_col)
    echo("Decomposing time series...")

    results = decompose_each(df_pivot, index_col=index_col, model=model, freq=period)
    os.makedirs(output_dir, exist_ok=True)

    # Save decomposition components for each polygon
    for pid, res in results.items():
        df_out = pd.DataFrame(
            {
                "date": res.observed.index,
                "observed": res.observed.values,
                "trend": res.trend.values,
                "seasonal": res.seasonal.values,
                "resid": res.resid.values,
            }
        )
        csv_path = os.path.join(output_dir, f"{pid}_decomposition.csv")
        df_out.to_csv(csv_path, index=False)
        echo(f"✅  Decomposition data saved to {csv_path}")

        if plot:
            plot_path = os.path.join(output_dir, f"{pid}_decomposition.png")
            plot_decomposition(res, plot_path)
            echo(f"✅  Decomposition plot saved to {plot_path}")


@stats.command(name="trend")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index-col", "-c", default="mean_ndvi", help="Column in CSV for trend computation"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="trend.csv",
    help="Output CSV path for trend values",
)
def trend(input_csv, index_col, output):
    """
    Compute linear trend for each polygon in a time-series CSV.
    """
    echo(f"Loading {input_csv}...")
    df = pd.read_csv(input_csv, parse_dates=["date"])
    echo("Computing trend...")
    df_trend = compute_trend(df, column=index_col)
    echo(f"Saving trend data to {output}...")
    df_trend.to_csv(output, index=False)
    echo(f"✅  Trend data saved to {output}")


@cli.group()
def visualize():
    """Visualization commands."""
    pass


@visualize.command(name="plot")
@click.option(
    "--datafile",
    "-d",
    required=True,
    type=click.Path(exists=True),
    help="Path to time-series CSV.",
)
@click.option(
    "--index-col",
    "-i",
    default="mean_ndvi",
    help="Column in CSV to plot (e.g. mean_ndvi, mean_evi)",
)
@click.option(
    "--agg-freq",
    "-f",
    type=click.Choice(["D", "ME", "Y"]),
    default="D",
    help="Aggregate frequency for plotting: D (daily), ME (monthly), YE (yearly)",
)
@click.option(
    "--interactive/--no-interactive",
    default=True,
    help="Generate interactive HTML (default) or static PNG",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="timeseries",
    help="Output path for plot (HTML if interactive, PNG otherwise)",
)
def plot(datafile, index_col, agg_freq, interactive, output):
    """
    Plot time-series from CSV: interactive HTML or static PNG.
    """
    df = pd.read_csv(datafile, parse_dates=["date"])
    if interactive:
        html_path = output if output.lower().endswith(".html") else output + ".html"
        plot_timeseries_html(df, index_col, html_path, agg_freq)
        echo(f"✅  Interactive plot saved to {output}")
    else:
        png_path = output if output.lower().endswith(".png") else output + ".png"
        plot_time_series(df, index_col, png_path, agg_freq)
        echo(f"✅  Static plot saved to {png_path}")


# ---- Animate command ----
@visualize.command(name="animate")
@click.argument("images_dir", type=click.Path(exists=True))
@click.option(
    "--pattern",
    "-p",
    default="*.png",
    help="Glob pattern to match image files (e.g., 'NDVI_*.png')",
)
@click.option(
    "--output-dir",
    "-o",
    default="gifs",
    help="Directory into which to write per-site animated GIFs",
)
@click.option(
    "--duration",
    type=float,
    default=2,
    help="Frame duration in seconds",
)
@click.option(
    "--loop",
    type=int,
    default=0,
    help="Number of loops (0 = infinite)",
)
def animate(images_dir, pattern, output_dir, duration, loop):
    """
    Generate one animated GIF per site by scanning IMAGES_DIR for files matching PATTERN.
    """
    try:
        make_gifs_per_site(
            images_dir=images_dir,
            pattern=pattern,
            output_dir=output_dir,
            duration=duration,
            loop=loop,
        )
        echo(f"✅  Animated GIFs written under {output_dir}")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error("Animate command failed", exc_info=True)
        echo(f"❌  Animation generation failed: {e}", err=True)
        sys.exit(1)


# ---- Gallery command ----
@cli.command(name="gallery")
@click.argument("chips_dir", type=click.Path(exists=True))
@click.option(
    "--template",
    "-t",
    type=click.Path(exists=True),
    default=None,
    help="Path to Jinja gallery template (defaults to built‑in)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="gallery.html",
    help="Output HTML file path",
)
@click.option(
    "--title",
    default=None,
    help="Title for the gallery page",
)
def gallery(chips_dir, template, output, title):
    """
    Build a static HTML image gallery from a directory of chips.
    """
    try:
        build_gallery(
            chips_dir=chips_dir,
            output_html=output,
            title=title,
            template_path=template,
        )
        echo(f"✅  Gallery written to {output}")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error("Gallery command failed", exc_info=True)
        echo(f"❌  Gallery generation failed: {e}", err=True)
        sys.exit(1)


@cli.command(name="report")
@click.argument("geojson", type=click.Path(exists=True))
@click.argument("timeseries_csv", type=click.Path(exists=True))
@click.argument("timeseries_html", type=click.Path(exists=True))
@click.option(
    "--gifs-dir",
    "-g",
    type=click.Path(exists=True),
    default=None,
    help="Directory of per-site animated GIFs",
)
@click.option(
    "--decomposition-dir",
    "-d",
    type=click.Path(exists=True),
    required=True,
    help="Directory containing per-site decomposition PNGs",
)
@click.option(
    "--chips-dir",
    "-c",
    type=click.Path(exists=True),
    required=True,
    help="Directory containing per-site image chips",
)
@click.option(
    "--map-png",
    type=click.Path(exists=True),
    default=None,
    help="Optional static PNG of project area to embed in report",
)
@click.option(
    "--title", type=str, default="VerdeSat Report", help="Title for the HTML report"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="report.html",
    help="Output HTML report path",
)
def report(
    geojson: str,
    timeseries_csv: str,
    timeseries_html: str,
    gifs_dir: str,
    decomposition_dir: str,
    chips_dir: str,
    map_png: str,
    title: str,
    output: str,
):
    """
    Generate a one‑page HTML report summarizing statistics, time‑series, decomposition, and image gallery.
    """
    echo(f"Building report '{output}'...")
    from verdesat.visualization.report import build_report

    try:
        build_report(
            geojson_path=geojson,
            timeseries_csv=timeseries_csv,
            timeseries_html=timeseries_html,
            gifs_dir=gifs_dir,
            decomposition_dir=decomposition_dir,
            chips_dir=chips_dir,
            map_png=map_png,
            output_path=output,
            title=title,
        )
        echo(f"✅  Report saved to {output}")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        echo(f"❌  Failed to build report: {e}")
        sys.exit(1)


@cli.group()
def pipeline():
    """High-level workflows that glue together multiple commands."""


@pipeline.command("report")
@click.option("--geojson", "-g", required=True, help="AOI GeoJSON")
@click.option("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
@click.option("--out-dir", "-o", default="verdesat_output", help="Output folder")
@click.option("--map-png", help="Optional map PNG to embed")
@click.option("--title", "-t", default="VerdeSat Report", help="Report title")
def pipeline_report(geojson, start, end, out_dir, map_png, title):
    """Run full NDVI → report pipeline in one go."""
    ctx = click.get_current_context()
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    ctx = click.get_current_context()

    # 1. Time series
    timeseries_csv = os.path.join(out_dir, "timeseries.csv")
    ctx.invoke(
        timeseries,
        geojson=geojson,
        start=start,
        end=end,
        agg="ME",
        output=timeseries_csv,
        backend="ee",
    )
    # 2. Aggregate & fill
    monthly_csv = os.path.join(out_dir, "timeseries_monthly.csv")
    ctx.invoke(aggregate, input_csv=timeseries_csv, freq="ME", output=monthly_csv)
    ctx.invoke(
        fill_gaps_cmd,
        input_csv=monthly_csv,
        output=os.path.join(out_dir, "timeseries_filled.csv"),
    )
    # 3. Decompose
    decomp_dir = os.path.join(out_dir, "decomp")
    ctx.invoke(
        decompose,
        input_csv=os.path.join(out_dir, "timeseries_filled.csv"),
        output_dir=decomp_dir,
    )

    # 4. Annual image chips (NDVI per year)
    annual_chips_dir = os.path.join(out_dir, "chips_annual")
    ctx.invoke(
        chips,
        geojson=geojson,
        start=start,
        end=end,
        period="Y",
        chip_type="ndvi",
        palette_arg="white-green",
        fmt="png",
        out_dir=annual_chips_dir,
    )

    # 5. Monthly composites for GIFs
    monthly_chips_dir = os.path.join(out_dir, "chips_monthly")
    ctx.invoke(
        chips,
        geojson=geojson,
        start=start,
        end=end,
        period="ME",
        chip_type="ndvi",
        palette_arg="white-green",
        fmt="png",
        out_dir=monthly_chips_dir,
    )

    # 6. Animated GIFs: one per site per year
    gifs_dir = os.path.join(out_dir, "gifs")
    start_year = datetime.strptime(start, "%Y-%m-%d").year
    end_year = datetime.strptime(end, "%Y-%m-%d").year
    for year in range(start_year, end_year + 1):
        year_pattern = f"*_{year}-*.png"
        year_gif_dir = os.path.join(gifs_dir, str(year))
        ctx.invoke(
            animate,
            images_dir=monthly_chips_dir,
            pattern=year_pattern,
            output_dir=year_gif_dir,
        )

    # Generate combined interactive time series plot for all sites
    timeseries_all_html = os.path.join(out_dir, "timeseries_all.html")
    ctx.invoke(
        plot,
        datafile=os.path.join(out_dir, "timeseries_filled.csv"),
        index_col="mean_ndvi",
        agg_freq="ME",
        interactive=True,
        output=timeseries_all_html,
    )

    # 7. Final report
    report_html = os.path.join(out_dir, "report.html")
    ctx.invoke(
        report,
        geojson=geojson,
        timeseries_csv=os.path.join(out_dir, "timeseries_filled.csv"),
        timeseries_html=timeseries_all_html,
        gifs_dir=gifs_dir,
        decomposition_dir=decomp_dir,
        chips_dir=annual_chips_dir,
        map_png=map_png,
        title=title,
        output=report_html,
    )
    click.echo(f"\n✅  All done! Your full report is here: {report_html}")


if __name__ == "__main__":
    cli()
