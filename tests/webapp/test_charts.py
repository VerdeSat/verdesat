from __future__ import annotations

import pandas as pd

from verdesat.webapp.components import charts


def _capture_plotly(monkeypatch):
    figs: list = []
    monkeypatch.setattr(
        charts.st, "plotly_chart", lambda fig, **kwargs: figs.append(fig)
    )
    return figs


def test_load_functions_use_signed_url(monkeypatch, tmp_path):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01"]),
            "observed": [1],
            "trend": [2],
            "seasonal": [3],
        }
    )
    path = tmp_path / "decomp.csv"
    df.to_csv(path, index=False)
    monkeypatch.setattr(charts, "signed_url", lambda key: str(path))
    loaded = charts.load_ndvi_decomposition(1)
    assert list(loaded.columns) == ["date", "observed", "trend", "seasonal"]

    df2 = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-01"]), "mean_msavi": [0.2], "id": [1]}
    )
    path2 = tmp_path / "msavi.csv"
    df2.to_csv(path2, index=False)
    monkeypatch.setattr(charts, "signed_url", lambda key: str(path2))
    loaded2 = charts.load_msavi_timeseries()
    assert "mean_msavi" in loaded2.columns


def test_ndvi_decomposition_chart_filters_years(monkeypatch):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2019-01-01", "2020-01-01"]),
            "observed": [1, 2],
            "trend": [1, 2],
            "seasonal": [1, 2],
        }
    )
    figs = _capture_plotly(monkeypatch)
    charts.ndvi_decomposition_chart(data=df, start_year=2020, end_year=2020)
    fig = figs[0]
    assert all(pd.to_datetime(tr.x[0]).year == 2020 for tr in fig.data)


def test_msavi_bar_chart(monkeypatch):
    df = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "date": pd.to_datetime(["2020-01-01", "2021-01-01", "2020-01-01"]),
            "mean_msavi": [0.1, 0.2, 0.3],
        }
    )
    figs = _capture_plotly(monkeypatch)
    charts.msavi_bar_chart(aoi_id=1, data=df, start_year=2020, end_year=2020)
    fig = figs[0]
    assert fig.data[0].type == "bar"


def test_component_and_all_charts(monkeypatch):
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "date": pd.to_datetime(["2020-01-01", "2020-01-01"]),
            "trend": [0.1, 0.2],
            "mean_msavi": [0.3, 0.4],
        }
    )
    figs = _capture_plotly(monkeypatch)
    charts.ndvi_component_chart(df, "trend")
    charts.msavi_bar_chart_all(df)
    assert len(figs) == 2
    assert figs[0].data[0].name == "1"
    assert figs[1].data[0].type == "bar"
