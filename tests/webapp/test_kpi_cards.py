import pandas as pd
import pytest

from verdesat.webapp.components.kpi_cards import aggregate_metrics


def test_aggregate_metrics_computes_means():
    df = pd.DataFrame(
        {
            "intactness": [0.2, 0.4],
            "shannon": [0.3, 0.5],
            "fragmentation": [0.1, 0.3],
            "msa": [0.7, 0.9],
            "ndvi_mean": [0.1, 0.2],
            "ndvi_std": [0.01, 0.03],
            "ndvi_slope": [0.05, -0.05],
            "ndvi_delta": [0.02, 0.04],
            "ndvi_p_value": [0.1, 0.2],
            "ndvi_pct_fill": [80.0, 90.0],
            "msavi_mean": [0.6, 0.8],
            "msavi_std": [0.02, 0.04],
            "bscore": [50.0, 70.0],
        }
    )
    metrics = aggregate_metrics(df)
    assert metrics.intactness == pytest.approx(0.3)
    assert metrics.msa == pytest.approx(0.8)
    assert metrics.bscore == pytest.approx(60.0)


def test_aggregate_metrics_handles_missing_msa():
    df = pd.DataFrame(
        {
            "intactness": [0.2, 0.4],
            "shannon": [0.3, 0.5],
            "fragmentation": [0.1, 0.3],
            # no MSA column
            "ndvi_mean": [0.1, 0.2],
            "ndvi_std": [0.01, 0.03],
            "ndvi_slope": [0.05, -0.05],
            "ndvi_delta": [0.02, 0.04],
            "ndvi_p_value": [0.1, 0.2],
            "ndvi_pct_fill": [80.0, 90.0],
            "msavi_mean": [0.6, 0.8],
            "msavi_std": [0.02, 0.04],
            "bscore": [50.0, 70.0],
        }
    )
    metrics = aggregate_metrics(df)
    assert metrics.msa == 0.0  # default when missing
