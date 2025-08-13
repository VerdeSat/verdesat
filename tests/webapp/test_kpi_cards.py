import pandas as pd
import pytest

from verdesat.webapp.components.kpi_cards import aggregate_metrics


def test_aggregate_metrics_computes_means():
    df = pd.DataFrame(
        {
            "intactness_pct": [0.2, 0.4],
            "shannon": [0.3, 0.5],
            "frag_norm": [0.1, 0.3],
            "ndvi_mean": [0.1, 0.2],
            "ndvi_slope": [0.05, -0.05],
            "ndvi_delta": [0.02, 0.04],
            "ndvi_p_value": [0.1, 0.2],
            "valid_obs_pct": [20.0, 10.0],
            "msavi_mean": [0.6, 0.8],
            "bscore": [50.0, 70.0],
            "msa": [0.5, 0.7],
        }
    )
    metrics = aggregate_metrics(df)
    assert metrics.intactness_pct == pytest.approx(0.3)
    assert metrics.frag_norm == pytest.approx(0.2)
    assert metrics.bscore == pytest.approx(60.0)
    assert metrics.bscore_band == "moderate"
    assert metrics.valid_obs_pct == pytest.approx(15.0)
    assert metrics.msa == pytest.approx(0.6)
    assert metrics.ndvi_p_value == pytest.approx(0.15)


def test_aggregate_metrics_handles_missing_fill():
    df = pd.DataFrame(
        {
            "intactness_pct": [0.2, 0.4],
            "shannon": [0.3, 0.5],
            "frag_norm": [0.1, 0.3],
            "ndvi_mean": [0.1, 0.2],
            "ndvi_slope": [0.05, -0.05],
            "ndvi_delta": [0.02, 0.04],
            "ndvi_p_value": [0.1, 0.2],
            # no valid_obs_pct column
            "msavi_mean": [0.6, 0.8],
            "bscore": [50.0, 70.0],
            "msa": [0.5, 0.7],
        }
    )
    metrics = aggregate_metrics(df)
    assert metrics.valid_obs_pct is None
