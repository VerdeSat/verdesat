from __future__ import annotations

"""Plotting helpers for the dashboard Charts tab."""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from verdesat.webapp.services.r2 import signed_url


@st.cache_data
def load_ndvi_decomposition(aoi_id: int) -> pd.DataFrame:
    """Load NDVI decomposition CSV for ``aoi_id`` from R2."""
    url = signed_url(f"resources/decomp/{aoi_id}_decomposition.csv")
    return pd.read_csv(url, parse_dates=["date"])


@st.cache_data
def load_msavi_timeseries() -> pd.DataFrame:
    """Load MSAVI time series CSV from R2."""
    url = signed_url("resources/msavi.csv")
    return pd.read_csv(url, parse_dates=["date"])


def ndvi_decomposition_chart(aoi_id: int) -> None:
    """Render NDVI observed, trend and seasonal curves."""
    df = load_ndvi_decomposition(aoi_id)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["observed"], name="Observed"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["trend"], name="Trend"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["seasonal"], name="Seasonal"))
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)


def msavi_bar_chart(aoi_id: int) -> None:
    """Render annual mean MSAVI as a bar chart."""
    df = load_msavi_timeseries()
    if "id" in df.columns:
        df = df[df["id"] == aoi_id]

    value_col: Optional[str] = None
    for col in ("mean_msavi", "msavi"):
        if col in df.columns:
            value_col = col
            break
    if value_col is None:
        value_col = df.columns[2]

    df["year"] = df["date"].dt.year
    agg = df.groupby("year")[value_col].mean()

    fig = go.Figure(go.Bar(x=agg.index.astype(str), y=agg.values, name="MSAVI"))
    fig.update_layout(
        xaxis_title="Year", yaxis_title="MSAVI", margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)
