import click
from core import utils, config

@click.group()
def cli():
    """VerdeSat: remote‑sensing analytics toolkit."""
    utils.setup_logging()

@cli.command()
@click.option('--geojson', '-g', required=True, help='Path to GeoJSON.')
@click.option('--start', '-s', default='2015-01-01', help='Start date (YYYY-MM-DD).')
@click.option('--end', '-e', default='2024-12-31', help='End date (YYYY-MM-DD).')
def download(geojson, start, end):
    """Download monthly composites for given polygons."""
    # TODO: hook into ingestion.downloader
    click.echo(f"Downloading from {start} to {end} for {geojson}")

@cli.command()
@click.option('--datafile', '-d', required=True, help='Path to time‑series CSV.')
def analyze(datafile):
    """Run seasonal decomposition and trend analysis."""
    click.echo(f"Analyzing {datafile}")

@cli.command()
def forecast():
    """Run forecasting pipelines (Prophet, LSTM, etc.)."""
    click.echo("Forecasting…")

if __name__ == '__main__':
    cli()