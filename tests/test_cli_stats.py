import pandas as pd
from click.testing import CliRunner

from verdesat.core.cli import cli
from verdesat.analytics.timeseries import TimeSeries


def _write_csv(path, df):
    df.to_csv(path, index=False)


def test_decompose_outputs_timeseries_long_when_insufficient_data(tmp_path):
    csv_path = tmp_path / "monthly.csv"
    df = pd.DataFrame(
        {
            "id": [1] * 12,
            "date": pd.date_range("2024-01-01", periods=12, freq="ME"),
            "mean_ndvi": [0.1] * 12,
        }
    )
    _write_csv(csv_path, df)
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "stats",
            "decompose",
            str(csv_path),
            "--output-dir",
            str(out_dir),
            "--no-plot",
        ],
    )
    assert result.exit_code == 0
    out_path = out_dir / "timeseries_long.csv"
    assert out_path.exists()
    ts_long = pd.read_csv(out_path)
    assert set(ts_long.columns) == {
        "date",
        "var",
        "stat",
        "value",
        "aoi_id",
        "freq",
        "source",
    }
    assert ts_long["stat"].unique().tolist() == ["raw"]


def test_summary_appends_metrics(tmp_path):
    ts_path = tmp_path / "timeseries_long.csv"
    dates = pd.date_range("2024-01-01", periods=3, freq="ME")
    df_long = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "var": ["ndvi"] * 3 + ["msavi"] * 3,
            "stat": ["raw"] * 6,
            "value": [0.1, 0.2, 0.3, 0.2, 0.3, 0.4],
            "aoi_id": ["A1"] * 6,
            "freq": ["monthly"] * 6,
            "source": ["S2"] * 6,
        }
    )
    _write_csv(ts_path, df_long)
    metrics_path = tmp_path / "metrics.csv"
    _write_csv(metrics_path, pd.DataFrame({"aoi_id": ["A1"], "intactness_pct": [50.0]}))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "stats",
            "summary",
            str(ts_path),
            "--aoi-id",
            "A1",
            "--metrics",
            str(metrics_path),
        ],
    )
    assert result.exit_code == 0
    out_df = pd.read_csv(metrics_path)
    assert {
        "ndvi_mean",
        "ndvi_slope",
        "ndvi_delta",
        "ndvi_p_value",
        "msavi_mean",
    }.issubset(out_df.columns)


def test_summary_handles_numeric_aoi_id(tmp_path):
    ts_path = tmp_path / "timeseries_long.csv"
    dates = pd.date_range("2024-01-01", periods=3, freq="ME")
    df_long = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "var": ["ndvi"] * 3 + ["msavi"] * 3,
            "stat": ["raw"] * 6,
            "value": [0.1, 0.2, 0.3, 0.2, 0.3, 0.4],
            "aoi_id": [1] * 6,
            "freq": ["monthly"] * 6,
            "source": ["S2"] * 6,
        }
    )
    _write_csv(ts_path, df_long)
    metrics_path = tmp_path / "metrics.csv"
    _write_csv(metrics_path, pd.DataFrame({"aoi_id": [1], "intactness_pct": [50.0]}))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "stats",
            "summary",
            str(ts_path),
            "--aoi-id",
            "1",
            "--metrics",
            str(metrics_path),
        ],
    )
    assert result.exit_code == 0
    out_df = pd.read_csv(metrics_path)
    assert {
        "ndvi_mean",
        "ndvi_slope",
        "ndvi_delta",
        "ndvi_p_value",
    }.issubset(out_df.columns)


def test_to_long_appends_existing():
    base = pd.DataFrame(
        {"id": [1], "date": [pd.Timestamp("2024-01-01")], "mean_ndvi": [0.1]}
    )
    ts = TimeSeries.from_dataframe(base, index="ndvi")
    existing = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")],
            "var": ["msavi"],
            "stat": ["raw"],
            "value": [0.2],
            "aoi_id": [1],
            "freq": ["monthly"],
            "source": ["S2"],
        }
    )
    long_df = ts.to_long(freq="monthly", source="S2", existing=existing)
    assert set(long_df["var"]) == {"ndvi", "msavi"}
