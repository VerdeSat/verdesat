"""
VerdeSat CLI entrypoint — defines commands for vector preprocessing, time series download,
and basic workflows. Dynamically loads available indices from the registry.
"""

import os
import sys
import json
from pathlib import Path
from typing import cast

import pandas as pd
import geopandas as gpd
import click  # type: ignore
from click import echo
from verdesat.ingestion.vector_preprocessor import VectorPreprocessor
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.ingestion import create_ingestor
from verdesat.ingestion.indices import INDEX_REGISTRY
from verdesat.analytics.timeseries import TimeSeries, decomp_to_long
from verdesat.analytics.trend import compute_trend
from verdesat.analytics.stats import compute_veg_metrics
from verdesat.core.logger import Logger
from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.ingestion.eemanager import ee_manager
from verdesat.services.timeseries import download_timeseries as svc_download_timeseries
from verdesat.services.report import build_report as svc_build_report
from verdesat.services.landcover import LandcoverService
from verdesat.core.storage import LocalFS, S3Bucket, StorageAdapter
from verdesat.visualization._chips_config import ChipsConfig
from verdesat.visualization.visualizer import Visualizer
from verdesat.core.pipeline import ReportPipeline
from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig
from verdesat.biodiv.metrics import MetricsResult, FragmentStats
from verdesat.biodiv.gbif_validator import OccurrenceService
from verdesat.services import (
    compute_bscores as svc_compute_bscores,
    compute_msa_means as svc_compute_msa_means,
)
from verdesat.services.ai_report import AiReportService, LlmClient
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.adapters.llm_openai import OpenAiLlmClient
from verdesat.services.reporting import (
    build_aoi_evidence_pack,
    build_project_pack,
)
from verdesat.schemas.reporting import AoiContext, MetricsRow, ProjectContext

logger = Logger.get_logger(__name__)
viz = Visualizer()


def _read_table(path: str) -> pd.DataFrame:
    """Return a DataFrame loaded from CSV or Parquet at *path*."""

    return (
        pd.read_parquet(path)
        if Path(path).suffix.lower() == ".parquet"
        else pd.read_csv(path)
    )


def _select_storage(kind: str) -> StorageAdapter:
    """Instantiate a storage adapter for ``kind`` ('local' or 'r2')."""

    if kind == "r2":
        import boto3  # type: ignore

        endpoint = os.getenv("R2_ENDPOINT")
        bucket = os.getenv("R2_BUCKET", "verdesat-data")
        key = os.getenv("R2_KEY")
        secret = os.getenv("R2_SECRET")
        if not (endpoint and key and secret):
            raise click.BadParameter(
                "Missing R2 configuration: R2_ENDPOINT, R2_KEY, R2_SECRET"
            )
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
        )
        return S3Bucket(bucket=bucket, client=client)
    return LocalFS()


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
    default=ConfigManager.DEFAULT_INDEX,
    help=f"Spectral index to compute (choices: {', '.join(INDEX_REGISTRY.keys())})",
)
@click.option(
    "--value-col",
    "-v",
    default=None,
    help="Output column name (defaults to mean_<index>)",
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
    geojson,
    collection,
    start,
    end,
    scale,
    index,
    value_col,
    chunk_freq,
    agg,
    output,
    backend,
):
    """
    Download and aggregate spectral index timeseries for polygons in GEOJSON.
    """
    try:
        svc_download_timeseries(
            geojson=geojson,
            collection=collection,
            start=start,
            end=end,
            scale=scale,
            index=index,
            value_col=value_col,
            chunk_freq=chunk_freq,
            agg=agg,
            output=output,
            backend=backend,
            logger=logger,
        )
        echo(f"✅  Results saved to {output}")
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


@download.command(name="landcover")
@click.argument("geojson", type=click.Path(exists=True))
@click.option("--year", "-y", type=int, required=True, help="Year of landcover")
@click.option(
    "--out-dir",
    "-o",
    type=click.Path(),
    default="landcover",
    help="Output directory",
)
def landcover(geojson, year, out_dir):
    """Download 10 m land-cover rasters for all polygons in GEOJSON."""
    try:
        aois = AOI.from_geojson(geojson, id_col="id")
        if not aois:
            raise ValueError("No AOIs found")
        svc = LandcoverService(logger=logger, storage=LocalFS())
        for aoi in aois:
            svc.download(aoi, year, out_dir)
        echo(f"✅  Landcover rasters written under {out_dir}/")
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error("Landcover command failed", exc_info=True)
        echo(f"❌  Landcover download failed: {e}", err=True)
        sys.exit(1)


@cli.group()
def stats():
    """Statistical operations on time-series data."""


@stats.command(name="aggregate")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index",
    "-i",
    type=click.Choice(list(INDEX_REGISTRY.keys())),
    default=ConfigManager.DEFAULT_INDEX,
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

    logger.info("Loading %s", input_csv)
    df = pd.read_csv(input_csv, parse_dates=["date"])
    logger.info("Aggregating by frequency '%s' for index '%s'", freq, index)
    ts = TimeSeries.from_dataframe(df, index=index)
    df_agg = ts.aggregate(freq).df
    logger.info("Saving aggregated data to %s", output)
    df_agg.to_csv(output, index=False)
    echo(f"✅  Aggregated data saved to {output}")


@cli.group()
def preprocess():
    """Data transformation commands (gap-fill, resample, etc.)."""


@preprocess.command(name="fill-gaps")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--value-col",
    "-c",
    default=ConfigManager.VALUE_COL_TEMPLATE.format(index=ConfigManager.DEFAULT_INDEX),
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
    index_name = value_col.replace("mean_", "")
    ts = TimeSeries.from_dataframe(df, index=index_name)
    filled_ts = ts.fill_gaps(method=method)
    echo(f"Saving filled data to {output}...")
    filled_ts.to_csv(output)
    echo("Done.")


@stats.command(name="decompose")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index-col",
    "-c",
    default=ConfigManager.VALUE_COL_TEMPLATE.format(index=ConfigManager.DEFAULT_INDEX),
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
    "--timeseries-long",
    "-t",
    type=click.Path(),
    default=None,
    help="Existing TimeseriesLong CSV to append to",
)
@click.option(
    "--plot/--no-plot",
    default=True,
    help="Whether to generate PNG plots for each polygon (default: True)",
)
def decompose(input_csv, index_col, model, period, output_dir, timeseries_long, plot):
    """
    Perform seasonal decomposition on a pivoted CSV and save plot.
    """
    logger.info("Loading %s", input_csv)
    df = pd.read_csv(input_csv, parse_dates=["date"])
    index_name = index_col.replace("mean_", "")
    ts = TimeSeries.from_dataframe(df, index=index_name)
    logger.info("Decomposing time series")

    results = ts.decompose(period=period, model=model)
    os.makedirs(output_dir, exist_ok=True)

    def _freq_label(dates: pd.Series) -> str:
        freq = pd.infer_freq(dates.sort_values())
        if freq and freq.upper().startswith("M"):
            return "monthly"
        if freq and freq.upper().startswith("Y"):
            return "annual"
        return "daily"

    freq_label = _freq_label(ts.df["date"])
    existing_long = None
    if timeseries_long and os.path.exists(timeseries_long):
        existing_long = pd.read_csv(timeseries_long)
    long_parts = [ts.to_long(freq=freq_label, source="S2", existing=existing_long)]

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
        long_parts.append(
            decomp_to_long(
                df_out,
                aoi_id=str(pid),
                var=index_name,
                freq=freq_label,
                source="S2",
            )
        )

        if plot:
            plot_path = os.path.join(output_dir, f"{pid}_decomposition.png")
            viz.plot_decomposition(res, plot_path)
            logger.info("Decomposition plot saved to %s", plot_path)

    if len(long_parts) == 1:
        logger.warning(
            "No decomposition components generated; output will contain raw values only"
        )

    out_path = timeseries_long or os.path.join(output_dir, "timeseries_long.csv")
    combined = pd.concat(long_parts, ignore_index=True)
    combined.to_csv(out_path, index=False)
    logger.info("TimeseriesLong saved to %s", out_path)
    echo(f"✅  TimeseriesLong saved to {out_path}")


@stats.command(name="summary")
@click.argument("timeseries_csv", type=click.Path(exists=True))
@click.option("--aoi-id", required=True, help="AOI identifier for metrics row")
@click.option(
    "--metrics",
    type=click.Path(exists=True),
    default=None,
    help="Existing metrics CSV to append to",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path (defaults to --metrics)",
)
def summary(timeseries_csv, aoi_id, metrics, output):
    """Compute NDVI/MSAVI summary stats and optionally append to metrics."""

    logger.info("Computing summary stats from %s", timeseries_csv)
    row = compute_veg_metrics(timeseries_csv, aoi_id=aoi_id)
    df = pd.DataFrame([row])

    if metrics:
        logger.info("Appending summary stats to %s", metrics)
        existing = pd.read_csv(metrics)
        if "aoi_id" in existing.columns:
            merged = existing.merge(df, on="aoi_id", how="left")
        else:
            merged = pd.concat([existing, df], axis=1)
        out_path = output or metrics
        merged.to_csv(out_path, index=False)
        echo(f"✅  Metrics updated at {out_path}")
    else:
        out_path = output or "stats_metrics.csv"
        logger.info("Writing summary stats to %s", out_path)
        df.to_csv(out_path, index=False)
        echo(f"✅  Stats metrics saved to {out_path}")


@stats.command(name="trend")
@click.argument("input_csv", type=click.Path(exists=True))
@click.option(
    "--index-col",
    "-c",
    default=ConfigManager.VALUE_COL_TEMPLATE.format(index=ConfigManager.DEFAULT_INDEX),
    help="Column in CSV for trend computation",
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
    trend_res = compute_trend(df, column=index_col)
    echo(f"Saving trend data to {output}...")
    trend_res.to_csv(output)
    echo(f"✅  Trend data saved to {output}")


@cli.group()
def bscore():
    """Biodiversity score utilities."""
    pass


@bscore.command(name="compute")
@click.argument("metrics_json", type=click.Path(exists=True))
@click.option(
    "--weights",
    "-w",
    type=click.Path(exists=True),
    default=str(
        Path(__file__).resolve().parent.parent / "config" / "bscore_weights.yaml"
    ),
    help="Path to weights YAML",
)
def compute_bscore(metrics_json, weights):
    """Compute biodiversity score from a metrics JSON file."""
    with open(metrics_json, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    metrics = MetricsResult(
        intactness_pct=float(data["intactness_pct"]),
        shannon=float(data["shannon"]),
        fragmentation=FragmentStats(
            edge_density=float(data["fragmentation"]["edge_density"]),
            frag_norm=float(data["fragmentation"]["frag_norm"]),
        ),
        msa=float(data.get("msa", 0.0)),
    )
    calc = BScoreCalculator(WeightsConfig.from_yaml(weights))
    score = calc.score(metrics)
    echo(f"{score:.2f}")


@bscore.command(name="from-geojson")
@click.argument("geojson", type=click.Path(exists=True))
@click.option("--year", "-y", required=True, type=int, help="Landcover year")
@click.option(
    "--weights",
    "-w",
    type=click.Path(exists=True),
    default=str(
        Path(__file__).resolve().parent.parent / "config" / "bscore_weights.yaml"
    ),
    help="Path to weights YAML",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Optional CSV output path",
)
@click.option("--dataset-uri", default=None, help="Optional custom MSA raster URI")
@click.option(
    "--budget-bytes",
    type=int,
    default=50_000_000,
    help="Maximum bytes to read from the dataset",
)
@click.option("--project-id", default=None, help="Project identifier")
@click.option("--project-name", default=None, help="Project name")
def bscore_from_geojson(
    geojson,
    year,
    weights,
    output,
    dataset_uri,
    budget_bytes,
    project_id,
    project_name,
):
    """Compute B-Score for polygons in GEOJSON."""
    df = svc_compute_bscores(
        geojson,
        year=year,
        weights=WeightsConfig.from_yaml(weights),
        dataset_uri=dataset_uri,
        budget_bytes=budget_bytes,
        output=output,
        logger=logger,
        project_id=project_id,
        project_name=project_name,
    )
    if output is None:
        echo(df.to_csv(index=False))
    else:
        echo(f"✅  Results saved to {output}")


@cli.command(name="msa")
@click.argument("geojson", type=click.Path(exists=True))
@click.option("--dataset-uri", default=None, help="Optional custom MSA raster URI")
@click.option(
    "--budget-bytes",
    type=int,
    default=50_000_000,
    help="Maximum bytes to read from the dataset",
)
@click.option(
    "--output", "-o", type=click.Path(), default="msa.csv", help="Output CSV path"
)
def msa_cmd(geojson, dataset_uri, budget_bytes, output):
    """Compute mean MSA for polygons in GEOJSON."""
    df = svc_compute_msa_means(
        geojson,
        dataset_uri=dataset_uri,
        budget_bytes=budget_bytes,
        output=output,
        logger=logger,
        storage=LocalFS(),
    )
    if output is None:
        echo(df.to_csv(index=False))
    else:
        echo(f"✅  Results saved to {output}")


@cli.group()
def validate():
    """Occurrence validation utilities."""
    pass


@validate.command(name="occurrence-density")
@click.argument("geojson", type=click.Path(exists=True))
@click.option(
    "--start-year", "-s", default=2000, type=int, help="Start year for records"
)
@click.option(
    "--output",
    "-o",
    default="occurrence_density.csv",
    type=click.Path(),
    help="CSV output path",
)
def validate_occurrence_density(geojson, start_year, output):
    """Compute occurrence density for AOIs in GEOJSON."""
    svc = OccurrenceService(logger=logger)
    aois = AOI.from_geojson(geojson, id_col="id")

    rows = []
    for aoi in aois:
        aoi_gdf = gpd.GeoDataFrame({"geometry": [aoi.geometry]}, crs="EPSG:4326")
        occ = svc.fetch_occurrences(aoi_gdf, start_year=start_year)
        area_km2 = (
            gpd.GeoSeries([aoi.geometry], crs="EPSG:4326")
            .to_crs(epsg=6933)
            .area.iloc[0]
            / 1e6
        )
        dens = svc.occurrence_density_km2(occ, area_km2)
        rows.append({"id": aoi.static_props.get("id"), "density": dens})

    df = pd.DataFrame.from_records(rows)
    df.to_csv(output, index=False)
    echo(f"✅  Occurrence densities saved to {output}")


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
    default=ConfigManager.VALUE_COL_TEMPLATE.format(index=ConfigManager.DEFAULT_INDEX),
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
        viz.plot_timeseries_html(df, index_col, html_path, agg_freq)
        echo(f"✅  Interactive plot saved to {output}")
    else:
        png_path = output if output.lower().endswith(".png") else output + ".png"
        viz.plot_time_series(df, index_col, png_path, agg_freq)
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
        viz.make_gifs_per_site(
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
        viz.build_gallery(
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


@cli.group()
def report() -> None:
    """Report generation commands."""


@report.command(name="html")
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
    "--title",
    type=str,
    default=ConfigManager.DEFAULT_REPORT_TITLE,
    help="Title for the HTML report",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="report.html",
    help="Output HTML report path",
)
def report_html(
    geojson: str,
    timeseries_csv: str,
    timeseries_html: str,
    gifs_dir: str,
    decomposition_dir: str,
    chips_dir: str,
    map_png: str,
    title: str,
    output: str,
) -> None:
    """Generate an HTML report with charts and image chips."""
    echo(f"Building report '{output}'...")

    try:
        svc_build_report(
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
    except Exception as e:  # pylint: disable=broad-exception-caught
        echo(f"❌  Failed to build report: {e}")
        sys.exit(1)


@report.command(name="ai")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--aoi", "aoi_id", required=True, help="AOI ID")
@click.option(
    "--metrics",
    "metrics_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to metrics CSV/Parquet",
)
@click.option(
    "--timeseries",
    "timeseries_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to time-series CSV/Parquet",
)
@click.option(
    "--lineage",
    "lineage_path",
    type=click.Path(exists=True),
    default=None,
    help="Optional lineage JSON",
)
@click.option("--model", default=None, help="LLM model name")
@click.option(
    "--prompt",
    "prompt_version",
    default=None,
    help="Prompt template version",
)
@click.option("--force", is_flag=True, help="Regenerate even if cached")
def report_ai(
    project_id: str,
    aoi_id: str,
    metrics_path: str,
    timeseries_path: str,
    lineage_path: str | None,
    model: str | None,
    prompt_version: str | None,
    force: bool,
) -> None:
    """Generate AI executive summary for AOI metrics."""
    config = ConfigManager()
    storage = LocalFS()
    llm = OpenAiLlmClient(seed=int(config.get("ai_report_seed", 42)), logger=logger)
    svc = AiReportService(
        llm=cast(LlmClient, llm), storage=storage, logger=logger, config=config
    )
    req = AiReportRequest(
        aoi_id=aoi_id,
        project_id=project_id,
        metrics_path=metrics_path,
        timeseries_path=timeseries_path,
        lineage_path=lineage_path,
        model=model,
        prompt_version=prompt_version,
        force=force,
    )

    try:
        result = svc.generate_summary(req)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("AI report failed", exc_info=True)
        echo(f"❌  AI report failed: {e}", err=True)
        sys.exit(1)

    echo(f"Artifact: {result.uri}")
    if result.url:
        echo(f"URL: {result.url}")
    echo(result.narrative)
    echo(json.dumps(result.summary, indent=2))


@cli.group()
def pack() -> None:
    """Build evidence packs for AOIs or projects."""


@pack.command("aoi")
@click.option("--aoi-id", required=True, help="AOI identifier")
@click.option(
    "--metrics",
    "metrics_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to metrics CSV/Parquet",
)
@click.option(
    "--ts",
    "ts_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to time-series CSV/Parquet",
)
@click.option(
    "--lineage",
    "lineage_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to lineage JSON",
)
@click.option(
    "--out",
    "out_store",
    type=click.Choice(["local", "r2"]),
    default="local",
    help="Storage backend",
)
@click.option("--include-ai", is_flag=True, help="Include AI summary")
def pack_aoi(
    aoi_id: str,
    metrics_path: str,
    ts_path: str,
    lineage_path: str,
    out_store: str,
    include_ai: bool,
) -> None:
    """Create an Evidence Pack for a single AOI."""

    storage = _select_storage(out_store)
    metrics_df = _read_table(metrics_path)
    if metrics_df.shape[0] != 1:
        echo("❌  metrics file must contain exactly one row", err=True)
        sys.exit(1)
    row = metrics_df.iloc[0].to_dict()
    try:
        project = ProjectContext(
            project_id=str(row["project_id"]),
            project_name=str(row.get("project_name", "")),
        )
    except KeyError as exc:  # pragma: no cover - defensive
        echo(f"❌  metrics missing field: {exc}", err=True)
        sys.exit(1)
    aoi_ctx = AoiContext(
        aoi_id=aoi_id,
        project_id=row.get("project_id"),
        aoi_name=row.get("aoi_name"),
    )
    metrics = MetricsRow(**{k: row.get(k) for k in MetricsRow.__dataclass_fields__})
    ts_df = _read_table(ts_path)
    with open(lineage_path, "r", encoding="utf-8") as fh:
        lineage = json.load(fh)

    ai_service = None
    ai_request = None
    if include_ai:
        config = ConfigManager()
        llm = OpenAiLlmClient(seed=int(config.get("ai_report_seed", 42)), logger=logger)
        ai_service = AiReportService(
            llm=cast(LlmClient, llm),
            storage=storage,
            logger=logger,
            config=config,
        )
        ai_request = AiReportRequest(
            aoi_id=aoi_id,
            project_id=project.project_id,
            metrics_path=metrics_path,
            timeseries_path=ts_path,
            lineage_path=lineage_path,
        )

    try:
        result = build_aoi_evidence_pack(
            aoi=aoi_ctx,
            project=project,
            metrics=metrics,
            ts_long=ts_df,
            lineage=lineage,
            include_ai=include_ai,
            storage=storage,
            ai_service=ai_service,
            ai_request=ai_request,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("pack aoi failed", exc_info=True)
        echo(f"❌  Pack failed: {e}", err=True)
        sys.exit(1)

    echo(f"Artifact: {result.uri}")
    if result.url:
        echo(f"URL: {result.url}")


@pack.command("project")
@click.option(
    "--metrics",
    "metrics_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to metrics CSV/Parquet",
)
@click.option(
    "--ts",
    "ts_path",
    type=click.Path(exists=True),
    default=None,
    help="Optional time-series CSV/Parquet",
)
@click.option(
    "--lineage",
    "lineage_path",
    type=click.Path(exists=True),
    required=True,
    help="Path to lineage JSON",
)
@click.option(
    "--out",
    "out_store",
    type=click.Choice(["local", "r2"]),
    default="local",
    help="Storage backend",
)
def pack_project(
    metrics_path: str,
    ts_path: str | None,
    lineage_path: str,
    out_store: str,
) -> None:
    """Create a Project Pack from metrics and optional time series."""

    storage = _select_storage(out_store)
    metrics_df = _read_table(metrics_path)
    if metrics_df.empty:
        echo("❌  metrics file is empty", err=True)
        sys.exit(1)
    row = metrics_df.iloc[0].to_dict()
    try:
        project = ProjectContext(
            project_id=str(row["project_id"]),
            project_name=str(row.get("project_name", "")),
        )
    except KeyError as exc:  # pragma: no cover - defensive
        echo(f"❌  metrics missing field: {exc}", err=True)
        sys.exit(1)
    ts_df = _read_table(ts_path) if ts_path else None
    with open(lineage_path, "r", encoding="utf-8") as fh:
        lineage = json.load(fh)
    try:
        result = build_project_pack(
            project=project,
            metrics_df=metrics_df,
            ts_long=ts_df,
            lineage=lineage,
            storage=storage,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("pack project failed", exc_info=True)
        echo(f"❌  Pack failed: {e}", err=True)
        sys.exit(1)

    echo(f"Artifact: {result.uri}")
    if result.url:
        echo(f"URL: {result.url}")


@cli.group()
def pipeline():
    """High-level workflows that glue together multiple commands."""


@pipeline.command("report")
@click.option("--geojson", "-g", required=True, help="AOI GeoJSON")
@click.option("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
@click.option("--out-dir", "-o", default="verdesat_output", help="Output folder")
@click.option("--map-png", help="Optional map PNG to embed")
@click.option(
    "--title",
    "-t",
    default=ConfigManager.DEFAULT_REPORT_TITLE,
    help="Report title",
)
@click.option(
    "--collection",
    "-c",
    default="NASA/HLS/HLSL30/v002",
    help="Earth Engine ImageCollection ID",
)
def pipeline_report(geojson, start, end, out_dir, map_png, title, collection):
    """Run full NDVI → report pipeline in one go."""
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    aois = AOI.from_geojson(geojson, id_col="id")
    sensor = SensorSpec.from_collection_id(collection)
    ingestor = create_ingestor(
        "ee", sensor, ee_manager_instance=ee_manager, logger=logger
    )
    viz = Visualizer()

    pipeline = ReportPipeline(aois=aois, ingestor=ingestor, visualizer=viz)
    report_path = pipeline.run(
        start=start, end=end, out_dir=out_dir, map_png=map_png, title=title
    )
    click.echo(f"\n✅  All done! Your full report is here: {report_path}")


@cli.command()
def webapp():
    """Run local Streamlit dashboard."""
    import importlib
    import pathlib
    import subprocess
    import sys

    app_path = pathlib.Path(importlib.import_module("verdesat.webapp.app").__file__)
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)], check=True
    )


if __name__ == "__main__":
    cli()
