import pandas as pd
from click.testing import CliRunner

from verdesat.core.cli import cli


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
    ts_path = tmp_path / "monthly.csv"
    df = pd.DataFrame(
        {
            "id": [1] * 3,
            "date": pd.date_range("2024-01-01", periods=3, freq="ME"),
            "mean_ndvi": [0.1, 0.2, 0.3],
            "mean_msavi": [0.2, 0.3, 0.4],
        }
    )
    _write_csv(ts_path, df)
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
