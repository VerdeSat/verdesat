import pandas as pd
from click.testing import CliRunner

from verdesat.core.cli import cli


def test_timeseries_value_col_passed(tmp_path, monkeypatch, dummy_aoi):
    calls = {}

    class DummyIngestor:
        def download_timeseries(
            self,
            aoi,
            start_date,
            end_date,
            scale,
            index,
            value_col,
            chunk_freq="YE",
            freq=None,
        ):
            calls["value_col"] = value_col
            calls["chunk_freq"] = chunk_freq
            calls["freq"] = freq
            return pd.DataFrame({"id": [1], "date": [start_date], value_col: [0.5]})

    monkeypatch.setattr(
        "verdesat.services.timeseries.create_ingestor",
        lambda backend, sensor, ee_manager_instance=None, logger=None: DummyIngestor(),
    )
    monkeypatch.setattr(
        "verdesat.services.timeseries.AOI.from_geojson",
        lambda path, id_col: [dummy_aoi],
    )
    monkeypatch.setattr(
        "verdesat.services.timeseries.SensorSpec.from_collection_id", lambda cid: None
    )
    monkeypatch.setattr(pd.DataFrame, "to_csv", lambda self, path, index=False: None)
    monkeypatch.setattr(
        pd,
        "concat",
        lambda dfs, ignore_index=True: dfs[0],
    )

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text("{}")
    result = runner.invoke(
        cli,
        [
            "download",
            "timeseries",
            str(geojson),
            "--index",
            "evi",
            "--value-col",
            "mean_evi",
        ],
    )
    assert result.exit_code == 0
    assert calls["value_col"] == "mean_evi"


def test_landcover_cli(monkeypatch, tmp_path, dummy_aoi):
    calls = []

    class DummySvc:
        def __init__(self, logger=None):
            pass

        def download(self, aoi, year, out_dir):
            calls.append((aoi, year, out_dir))

    monkeypatch.setattr("verdesat.core.cli.LandcoverService", DummySvc)
    monkeypatch.setattr(
        "verdesat.core.cli.AOI.from_geojson", lambda p, id_col: [dummy_aoi]
    )

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text("{}")
    out_dir = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "download",
            "landcover",
            str(geojson),
            "--year",
            "2020",
            "--out-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert calls and calls[0][1] == 2020
