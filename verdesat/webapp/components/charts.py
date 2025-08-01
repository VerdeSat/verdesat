from __future__ import annotations

"""Plotting helpers for the dashboard Charts tab."""

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


def ndvi_decomposition_chart(
    aoi_id: int | None = None,
    data: pd.DataFrame | None = None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> None:
    """Render NDVI observed, trend and seasonal curves.

    Parameters
    ----------
    aoi_id:
        Identifier of the demo AOI when ``data`` is not provided.
    data:
        Optional DataFrame containing the decomposition results. When omitted,
        the CSV for ``aoi_id`` is loaded from R2.
    start_year, end_year:
        Optional range used to clip the time series and set the plot's x-axis
        limits.
    """

    if data is None:
        if aoi_id is None:
            raise ValueError("aoi_id or data must be provided")
        df = load_ndvi_decomposition(aoi_id)
    else:
        df = data

    if start_year is not None and end_year is not None:
        mask = (df["date"].dt.year >= start_year) & (df["date"].dt.year <= end_year)
        df = df.loc[mask]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["observed"], name="Observed"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["trend"], name="Trend"))
    fig.add_trace(go.Scatter(x=df["date"], y=df["seasonal"], name="Seasonal"))
    if start_year is not None and end_year is not None:
        fig.update_xaxes(
            range=[
                pd.Timestamp(f"{start_year}-01-01"),
                pd.Timestamp(f"{end_year}-12-31"),
            ]
        )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)


def msavi_bar_chart(
    aoi_id: int | None = None,
    data: pd.DataFrame | None = None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> None:
    """Render annual mean MSAVI as a bar chart.

    Parameters mirror :func:`ndvi_decomposition_chart`.
    """

    if data is None:
        if aoi_id is None:
            raise ValueError("aoi_id or data must be provided")
        df = load_msavi_timeseries()
        if "id" in df.columns:
            df = df[df["id"] == aoi_id]
    else:
        df = data

    if start_year is not None and end_year is not None:
        mask = (df["date"].dt.year >= start_year) & (df["date"].dt.year <= end_year)
        df = df.loc[mask]

    value_col = next((c for c in ("mean_msavi", "msavi") if c in df.columns), None)
    if value_col is None:
        value_col = df.columns[2]

    df["year"] = df["date"].dt.year
    agg = df.groupby("year")[value_col].mean()

    fig = go.Figure(go.Bar(x=agg.index, y=agg.values, name="MSAVI"))
    if start_year is not None and end_year is not None:
        fig.update_xaxes(range=[start_year, end_year])
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="MSAVI",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)
