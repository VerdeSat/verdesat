from __future__ import annotations

"""Reusable KPI card components for the Streamlit dashboard."""

from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st


@dataclass
class Metrics:
    """Container for biodiversity metrics."""

    intactness: float
    shannon: float
    fragmentation: float
    ndvi_mean: float
    ndvi_std: float
    ndvi_slope: float
    ndvi_delta: float
    ndvi_p_value: float
    ndvi_peak: str
    ndvi_pct_fill: float
    msavi_mean: float
    msavi_std: float
    bscore: float


def display_metrics(metrics: Metrics) -> None:
    """Render KPI cards for the provided metrics."""

    top = st.columns(6)
    top[0].metric("Intactness %", f"{metrics.intactness * 100:.1f}")
    top[1].metric("Shannon", f"{metrics.shannon:.2f}")
    top[2].metric("Frag-Norm", f"{metrics.fragmentation:.2f}")
    top[3].metric("NDVI μ", f"{metrics.ndvi_mean:.2f}")
    top[4].metric("MSAVI μ", f"{metrics.msavi_mean:.2f}")
    top[5].metric("B-Score", f"{metrics.bscore:.1f}")

    bottom = st.columns(5)
    bottom[0].metric("NDVI slope", f"{metrics.ndvi_slope:.3f}")
    bottom[1].metric("ΔNDVI", f"{metrics.ndvi_delta:.3f}")
    bottom[2].metric("p-value", f"{metrics.ndvi_p_value:.3f}")
    bottom[3].metric("Peak", metrics.ndvi_peak or "–")
    bottom[4].metric("% Fill", f"{metrics.ndvi_pct_fill:.1f}")


def bscore_gauge(score: float, *, title: str | None = None) -> None:
    """Display a gauge chart for the B-Score."""

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": ""},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#159466"},
                "bgcolor": "white",
            },
            title={"text": title or "B-Score"},
        )
    )
    st.plotly_chart(fig, use_container_width=True)
