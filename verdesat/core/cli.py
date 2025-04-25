import os
import sys
import json
import pandas as pd
import click  # type: ignore

from click import echo
from verdesat.core import utils
from verdesat.ingestion.shapefile_preprocessor import ShapefilePreprocessor
from verdesat.analytics.timeseries import chunked_timeseries, aggregate_timeseries
from verdesat.visualization.plotly_viz import plot_timeseries_html
from verdesat.visualization.static_viz import plot_time_series


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
    echo(f"Loading {geojson}...")
    with open(geojson) as f:
        gj = json.load(f)

    df = chunked_timeseries(
        gj, collection, start, end, scale=scale, freq=agg, index=index
    )

    echo(f"Saving to {output}...")
    df.to_csv(output, index=False)
    echo("Done.")


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
