import json
from pathlib import Path
import pandas as pd
import geopandas as gpd
from click.testing import CliRunner
from unittest.mock import MagicMock

from verdesat.core.cli import cli
from verdesat.core.storage import LocalFS


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


def test_landcover_cli(monkeypatch, tmp_path):
    svc = MagicMock()
    created = {}

    def fake_service(logger=None, storage=None):
        created["storage"] = storage
        return svc

    monkeypatch.setattr("verdesat.core.cli.LandcoverService", fake_service)

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]},"properties":{"id":1}}]}'
    )
    result = runner.invoke(
        cli,
        [
            "download",
            "landcover",
            str(geojson),
            "--year",
            "2021",
            "--out-dir",
            "dest",
        ],
    )
    assert result.exit_code == 0
    assert svc.download.called
    assert svc.download.call_args.args[2] == "dest"
    assert isinstance(created["storage"], LocalFS)


def test_landcover_cli_multiple_polygons(monkeypatch, tmp_path):
    svc = MagicMock()
    created = {}

    def fake_service(logger=None, storage=None):
        created["storage"] = storage
        return svc

    monkeypatch.setattr("verdesat.core.cli.LandcoverService", fake_service)

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]},"properties":{"id":1}},{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[1,1],[1,2],[2,2],[2,1],[1,1]]]},"properties":{"id":2}}]}'
    )
    result = runner.invoke(
        cli,
        [
            "download",
            "landcover",
            str(geojson),
            "--year",
            "2021",
            "--out-dir",
            "dest",
        ],
    )
    assert result.exit_code == 0
    assert svc.download.call_count == 2
    assert isinstance(created["storage"], LocalFS)


def test_bscore_cli(tmp_path):
    metrics = {
        "intactness_pct": 60.0,
        "shannon": 0.4,
        "fragmentation": {"edge_density": 0.1, "frag_norm": 0.1},
        "msa": 0.5,
    }
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics))
    weights_path = tmp_path / "weights.yaml"
    weights_path.write_text("intactness: 1\nshannon: 1\nfragmentation: 1\nmsa: 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["bscore", "compute", str(metrics_path), "--weights", str(weights_path)],
    )
    assert result.exit_code == 0
    assert result.output.strip()


def test_bscore_geojson_cli(monkeypatch, tmp_path):
    called = {}

    def fake_compute_bscores(
        geojson,
        year,
        weights,
        dataset_uri=None,
        budget_bytes=50_000_000,
        output=None,
        logger=None,
        storage=None,
        project_id=None,
        project_name=None,
    ):
        called["geojson"] = geojson
        called["year"] = year
        called["dataset_uri"] = dataset_uri
        called["budget_bytes"] = budget_bytes
        called["project_id"] = project_id
        called["project_name"] = project_name
        return pd.DataFrame({"aoi_id": [1], "bscore": [42.0]})

    monkeypatch.setattr("verdesat.core.cli.svc_compute_bscores", fake_compute_bscores)

    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]},"properties":{"id":1}}]}'
    )
    weights_path = tmp_path / "weights.yaml"
    weights_path.write_text("intactness: 1\nshannon: 1\nfragmentation: 1\nmsa: 1\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "bscore",
            "from-geojson",
            str(geojson),
            "--year",
            "2021",
            "--weights",
            str(weights_path),
            "--dataset-uri",
            "s3://msafile.tif",
            "--budget-bytes",
            "123",
            "--project-id",
            "P1",
            "--project-name",
            "Proj",
        ],
    )

    assert result.exit_code == 0
    assert called["year"] == 2021
    assert called["dataset_uri"] == "s3://msafile.tif"
    assert called["budget_bytes"] == 123
    assert called["project_id"] == "P1"
    assert called["project_name"] == "Proj"


def test_validate_occurrence_density_cli(monkeypatch, tmp_path, dummy_aoi):
    svc = {}

    class DummyService:
        def __init__(self, logger=None):
            pass

        def fetch_occurrences(self, *_a, **_k):
            svc.setdefault("fetch", 0)
            svc["fetch"] += 1
            return gpd.GeoDataFrame({"geometry": [dummy_aoi.geometry]}, crs="EPSG:4326")

        @staticmethod
        def occurrence_density_km2(_gdf, _area):
            svc["density"] = True
            return 0.5

    monkeypatch.setattr(
        "verdesat.core.cli.OccurrenceService", lambda logger=None: DummyService()
    )
    monkeypatch.setattr(
        "verdesat.core.cli.AOI.from_geojson", lambda p, id_col: [dummy_aoi]
    )
    monkeypatch.setattr(
        pd.DataFrame,
        "to_csv",
        lambda self, path, index=False: Path(path).write_text("x"),
    )

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text("{}")
    out = tmp_path / "dens.csv"
    result = runner.invoke(
        cli,
        ["validate", "occurrence-density", str(geojson), "--output", str(out)],
    )
    assert result.exit_code == 0
    assert svc["fetch"] == 1
    assert svc.get("density")
    assert out.exists()


def test_msa_cli(monkeypatch, tmp_path):
    called = {}

    def fake_compute_msa_means(
        geojson,
        *,
        dataset_uri=None,
        budget_bytes=50_000_000,
        output=None,
        logger=None,
        storage=None,
    ):
        called["geojson"] = geojson
        called["dataset_uri"] = dataset_uri
        return pd.DataFrame({"id": [1], "mean_msa": [0.5]})

    monkeypatch.setattr(
        "verdesat.core.cli.svc_compute_msa_means", fake_compute_msa_means
    )

    runner = CliRunner()
    geojson = tmp_path / "aoi.geojson"
    geojson.write_text("{}")
    result = runner.invoke(
        cli,
        [
            "msa",
            str(geojson),
            "--dataset-uri",
            "s3://bucket/file.tif",
            "--output",
            str(tmp_path / "out.csv"),
        ],
    )
    assert result.exit_code == 0
    assert called["geojson"] == str(geojson)
    assert called["dataset_uri"] == "s3://bucket/file.tif"
