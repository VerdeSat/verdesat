import click  # type: ignore
from core import utils, config  # type: ignore
import os
import sys
from ingestion.shapefile_preprocessor import ShapefilePreprocessor


@click.group()
def cli():
    """VerdeSat: remote‑sensing analytics toolkit."""
    utils.setup_logging()


@cli.command()
@click.option("--geojson", "-g", required=True, help="Path to GeoJSON.")
@click.option("--start", "-s", default="2015-01-01", help="Start date (YYYY-MM-DD).")
@click.option("--end", "-e", default="2024-12-31", help="End date (YYYY-MM-DD).")
def download(geojson, start, end):
    """Download monthly composites for given polygons."""
    # TODO: hook into ingestion.downloader
    click.echo(f"Downloading from {start} to {end} for {geojson}")


@cli.command()
@click.option("--datafile", "-d", required=True, help="Path to time‑series CSV.")
def analyze(datafile):
    """Run seasonal decomposition and trend analysis."""
    click.echo(f"Analyzing {datafile}")


@cli.command()
def forecast():
    """Run forecasting pipelines (Prophet, LSTM, etc.)."""
    click.echo("Forecasting…")


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
def prepare(input_dir):
    """Process all vector files in INPUT_DIR into a single, clean GeoJSON."""
    utils.setup_logging()
    processor = ShapefilePreprocessor(input_dir)
    try:
        processor.run()
        output_path = os.path.join(
            input_dir, f"{os.path.basename(input_dir)}_processed.geojson"
        )
        click.echo(f"✅  GeoJSON written to `{output_path}`")
    except Exception as e:
        click.echo(f"❌  Processing failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
