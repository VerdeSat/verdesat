from __future__ import annotations

"""Reusable KPI card components for the Streamlit dashboard."""

from dataclasses import dataclass
from typing import Optional

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
    msavi_mean: float
    msavi_std: float
    bscore: float


def display_metrics(metrics: Metrics) -> None:
    """Render KPI cards for the provided metrics."""

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Intactness %", f"{metrics.intactness * 100:.1f}")
    col2.metric("Shannon", f"{metrics.shannon:.2f}")
    col3.metric("Frag-Norm", f"{metrics.fragmentation:.2f}")
    col4.metric("NDVI μ", f"{metrics.ndvi_mean:.2f}")
    col5.metric("MSAVI μ", f"{metrics.msavi_mean:.2f}")
    col6.metric("B-Score", f"{metrics.bscore:.1f}")


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
