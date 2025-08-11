import pandas as pd
from click.testing import CliRunner

from verdesat.core.cli import cli


class DummyLlm:
    def __init__(self, *args, **kwargs):
        pass

    def generate(self, prompt: str, **kwargs):
        return {
            "executive_summary": "exec",
            "kpi_sentences": {
                "bscore": "b",
                "intactness": "i",
                "fragmentation": "f",
                "ndvi_trend": "n",
            },
            "esrs_e4": {
                "extent_condition": "extent",
                "pressures": "press",
                "targets": "targets",
                "actions": "actions",
                "financial_effects": "effects",
            },
            "flags": [],
            "numbers": {},
            "meta": {},
        }


def _write_metrics(path):
    df = pd.DataFrame(
        {
            "aoi_id": ["A1"],
            "project_id": ["P1"],
            "method_version": ["0.1"],
            "window_start": ["2024-01-01"],
            "window_end": ["2024-12-31"],
        }
    )
    df.to_csv(path, index=False)


def _write_timeseries(path):
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "metric": ["ndvi_mean"],
            "value": [0.5],
            "aoi_id": ["A1"],
        }
    )
    df.to_csv(path, index=False)


def test_report_ai_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    metrics = tmp_path / "metrics.csv"
    timeseries = tmp_path / "ts.csv"
    _write_metrics(metrics)
    _write_timeseries(timeseries)

    monkeypatch.setattr(
        "verdesat.core.cli.OpenAiLlmClient", lambda seed, logger: DummyLlm()
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            "ai",
            "--project",
            "P1",
            "--aoi",
            "A1",
            "--metrics",
            str(metrics),
            "--timeseries",
            str(timeseries),
        ],
    )
    assert result.exit_code == 0
    assert "exec" in result.output
