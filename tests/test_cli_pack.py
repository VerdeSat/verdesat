import json
from click.testing import CliRunner
import pandas as pd

from verdesat.core.cli import cli
from verdesat.services.reporting import PackResult
from verdesat.core.storage import LocalFS


def _write_csv(path, df):
    df.to_csv(path, index=False)


def _write_lineage(path):
    path.write_text(json.dumps({"method_version": "0.2.0"}))


def test_pack_aoi_calls_service(monkeypatch, tmp_path):
    captured = {}

    def fake_build_aoi_evidence_pack(**kwargs):
        captured.update(kwargs)
        return PackResult(uri="aoi.zip", url=None, sha256="x", bytesize=1)

    monkeypatch.setattr(
        "verdesat.core.cli.build_aoi_evidence_pack", fake_build_aoi_evidence_pack
    )

    metrics_path = tmp_path / "m.csv"
    ts_path = tmp_path / "ts.csv"
    lineage_path = tmp_path / "lin.json"
    _write_csv(
        metrics_path,
        pd.DataFrame(
            {
                "project_id": ["p1"],
                "project_name": ["Demo"],
                "aoi_name": ["Area"],
                "ndvi_mean": [0.5],
            }
        ),
    )
    _write_csv(
        ts_path,
        pd.DataFrame(
            {
                "date": ["2024-01-01"],
                "var": ["ndvi"],
                "stat": ["mean"],
                "value": [0.5],
                "aoi_id": ["a1"],
                "freq": ["monthly"],
                "source": ["s2"],
            }
        ),
    )
    _write_lineage(lineage_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pack",
            "aoi",
            "--aoi-id",
            "a1",
            "--metrics",
            str(metrics_path),
            "--ts",
            str(ts_path),
            "--lineage",
            str(lineage_path),
        ],
    )
    assert result.exit_code == 0
    assert captured["aoi"].aoi_id == "a1"
    assert captured["project"].project_id == "p1"
    assert isinstance(captured["storage"], LocalFS)


def test_pack_project_calls_service(monkeypatch, tmp_path):
    captured = {}

    def fake_build_project_pack(**kwargs):
        captured.update(kwargs)
        return PackResult(uri="proj.zip", url=None, sha256="x", bytesize=1)

    monkeypatch.setattr("verdesat.core.cli.build_project_pack", fake_build_project_pack)

    metrics_path = tmp_path / "pm.csv"
    ts_path = tmp_path / "pts.csv"
    lineage_path = tmp_path / "lin.json"
    _write_csv(
        metrics_path,
        pd.DataFrame(
            {"project_id": ["p1"], "project_name": ["Demo"], "ndvi_mean": [0.5]}
        ),
    )
    _write_csv(
        ts_path,
        pd.DataFrame(
            {
                "date": ["2024-01-01"],
                "var": ["ndvi"],
                "stat": ["mean"],
                "value": [0.5],
                "aoi_id": ["a1"],
                "freq": ["monthly"],
                "source": ["s2"],
            }
        ),
    )
    _write_lineage(lineage_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "pack",
            "project",
            "--metrics",
            str(metrics_path),
            "--ts",
            str(ts_path),
            "--lineage",
            str(lineage_path),
        ],
    )
    assert result.exit_code == 0
    assert captured["project"].project_id == "p1"
    assert captured["metrics_df"].equals(pd.read_csv(metrics_path))
    assert isinstance(captured["storage"], LocalFS)
