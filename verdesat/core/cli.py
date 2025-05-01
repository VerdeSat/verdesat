import os
import sys
import json
import pandas as pd
import click  # type: ignore
import ee
import logging
from click import echo
from verdesat.core import utils
from verdesat.ingestion.shapefile_preprocessor import ShapefilePreprocessor
from verdesat.ingestion.chips import get_composite, export_composites_to_png
from verdesat.analytics.timeseries import chunked_timeseries, aggregate_timeseries
from verdesat.visualization.static_viz import plot_decomposition
from verdesat.analytics.decomposition import decompose_each
from verdesat.analytics.trend import compute_trend
from verdesat.analytics.preprocessing import interpolate_gaps
from verdesat.visualization.plotly_viz import plot_timeseries_html
from verdesat.visualization.static_viz import plot_time_series
from verdesat.ingestion.downloader import initialize, get_image_collection
from verdesat.ingestion.indices import compute_index

# Predefined NDVI color palettes
PRESET_PALETTES = {
    "white-green": ["white", "green"],
    "red-white-green": ["red", "white", "green"],
    "brown-green": ["brown", "green"],
    "blue-white-green": ["blue", "white", "green"],
}

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """VerdeSat: remote-sensing analytics toolkit."""
    utils.setup_logging()


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
def prepare(input_dir):
    """Process all vector files in INPUT_DIR into a single, clean GeoJSON."""
    processor = ShapefilePreprocessor(input_dir)
    try:
        processor.run()
        output_path = os.path.join(
            input_dir, f"{os.path.basename(input_dir)}_processed.geojson"
        )
        echo(f"✅  GeoJSON written to `{output_path}`")
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
    pass


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
    type=click.Choice(["ndvi", "evi"]),
    default="ndvi",
    help="Spectral index to compute",
)
@click.option(
    "--agg",
    "-a",
    type=click.Choice(["D", "M", "Y"]),
    default="D",
    help="Temporal aggregation: D,M,Y",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="timeseries.csv",
    help="Output CSV path",
)
def timeseries(geojson, collection, start, end, scale, index, agg, output):
    """
    Download and aggregate spectral index timeseries for polygons in GEOJSON.
    Uses --index to select the spectral index (e.g., ndvi, evi).
    """
    try:
        echo(f"Loading {geojson}...")
        with open(geojson) as f:
            gj = json.load(f)

        df = chunked_timeseries(
            gj, collection, start, end, scale=scale, freq=agg, index=index
        )

        echo(f"Saving to {output}...")
        df.to_csv(output, index=False)
        echo("Done.")
    except Exception as e:
        logger.error("Timeseries command failed", exc_info=True)
        echo(f"❌  Timeseries download failed: {e}", err=True)
        sys.exit(1)


@download.command(name="chips")
@click.argument("geojson", type=click.Path(exists=True))
@click.option(
    "--collection",
    "-c",
    default="NASA/HLS/HLSL30/v002",
    help="Earth Engine ImageCollection ID",
)
@click.option("--start", "-s", default="2015-01-01", help="Start date")
@click.option("--end", "-e", default="2024-12-31", help="End date")
@click.option(
    "--period",
    "-p",
    type=click.Choice(["M", "Y"]),
    default="M",
    help="Composite period: M=monthly, Y=yearly",
)
@click.option(
    "--type",
    "-t",
    "chip_type",
    type=click.Choice(["truecolor", "ndvi"]),
    default="truecolor",
)
@click.option("--scale", type=int, default=30, help="Resolution in meters")
@click.option(
    "--min-val",
    type=float,
    default=None,
    help="Minimum stretch value (e.g. 0.0 for true color, -1.0 for NDVI)",
)
@click.option(
    "--max-val",
    type=float,
    default=None,
    help="Maximum stretch value (e.g. 1.0)",
)
@click.option(
    "--buffer",
    type=int,
    default=0,
    help="Buffer distance (meters) to apply around each polygon",
)
@click.option(
    "--buffer-percent",
    type=float,
    default=None,
    help="Buffer distance as a percentage of AOI size",
)
@click.option(
    "--gamma",
    type=float,
    default=None,
    help="Gamma correction value for visualization (e.g., 0.8)",
)
@click.option(
    "--percentile-low",
    type=float,
    default=None,
    help="Lower percentile for auto-stretch (e.g., 2)",
)
@click.option(
    "--percentile-high",
    type=float,
    default=None,
    help="Upper percentile for auto-stretch (e.g., 98)",
)
@click.option(
    "--palette",
    "palette_arg",
    type=str,
    default=None,
    help=(
        "NDVI palette: preset names (white-green, red-white-green, brown-green, blue-white-green)"
        " or comma-separated colors"
    ),
)
@click.option("--format", "-f", default="png", help="Format of the output files")
@click.option("--out-dir", "-o", default="chips", help="Output directory")
@click.option("--ee-project", default=None, help="GCP project override")
def chips(
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
    format,
    out_dir,
    ee_project,
):
    """Download per-polygon image chips (monthly/yearly true‐color or NDVI)."""
    try:
        with open(geojson) as f:
            gj = json.load(f)
        initialize(project=ee_project)
        echo("Initializing Earth Engine and fetching collection...")
        # Use GEE helper to fetch raw image collection
        aoi = ee.FeatureCollection(gj)
        coll = get_image_collection(collection, start, end, aoi)
        # If NDVI, map compute_index
        if chip_type == "ndvi":
            bands = ["NDVI"]
            # Determine palette
            if palette_arg:
                if palette_arg in PRESET_PALETTES:
                    palette = PRESET_PALETTES[palette_arg]
                else:
                    palette = [c.strip() for c in palette_arg.split(",") if c.strip()]
            else:
                palette = PRESET_PALETTES["white-green"]
        else:
            bands = ["B4", "B3", "B2"]
            palette = None

        # 1) get composites
        composites = get_composite(
            gj,
            collection,  # your ImageCollection ID
            start,  # start date str
            end,
            reducer=ee.Reducer.mean(),
            bands=bands,
            scale=scale,
            period=period,
            base_coll=coll,
            project=ee_project,
        )

        # 2) export
        export_composites_to_png(
            composites,
            gj,
            out_dir,
            bands=bands,
            palette=palette,
            scale=scale,
            min_val=min_val,
            max_val=max_val,
            buffer=buffer,
            buffer_percent=buffer_percent,
            gamma=gamma,
            percentile_low=percentile_low,
            percentile_high=percentile_high,
            fmt=format,
        )

        click.echo(f"✅  Chips written under {out_dir}/")
    except Exception as e:
        logger.error("Chips command failed", exc_info=True)
        echo(f"❌  Chips download failed: {e}", err=True)
        sys.exit(1)


@cli.group()
def stats():
    """Statistical operations on time-series data."""
    pass


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
    type=click.Choice(["D", "M", "Y"]),
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
    df_agg = aggregate_timeseries(df, freq=freq, index=index)
    echo(f"Saving aggregated data to {output}...")
    df_agg.to_csv(output, index=False)
    echo("Done.")


@cli.group()
def preprocess():
    """Data transformation commands (gap-fill, resample, etc.)."""
    pass


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
    type=click.Choice(["D", "M", "Y"]),
    default="D",
    help="Aggregate frequency for plotting: D (daily), M (monthly), Y (yearly)",
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


if __name__ == "__main__":
    cli()
