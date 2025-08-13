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
