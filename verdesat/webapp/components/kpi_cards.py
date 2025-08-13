"""Reusable KPI card components for the Streamlit dashboard."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Optional, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from verdesat.schemas.reporting import MetricsRow


def aggregate_metrics(df: pd.DataFrame) -> MetricsRow:
    """Return mean values for ``df`` as a :class:`MetricsRow` instance."""

    field_names = {f.name for f in fields(MetricsRow)}
    data: dict[str, Any] = {}

    for name in field_names:
        if name in df.columns:
            data[name] = float(df[name].mean(numeric_only=True))

    bscore = data.get("bscore")
    if bscore is not None and "bscore_band" not in data:
        if bscore < 40:
            data["bscore_band"] = "low"
        elif bscore < 70:
            data["bscore_band"] = "moderate"
        else:
            data["bscore_band"] = "high"

    return MetricsRow(**cast(dict[str, Any], data))


def display_metrics(metrics: MetricsRow) -> None:
    """Render KPI cards for the provided metrics."""

    top = st.columns(5)
    top[0].metric(
        "Intactness %",
        f"{(metrics.intactness_pct or 0.0) * 100:.1f}",
        help="Share of AOI area classified as natural or semi-natural habitat.",
    )
    top[1].metric(
        "Shannon",
        f"{(metrics.shannon or 0.0):.2f}",
        help="Shannon diversity index of land-cover classes; higher means more varied habitat.",
    )
    top[2].metric(
        "Frag-Norm",
        f"{(metrics.frag_norm or 0.0):.2f}",
        help="Normalized fragmentation index; higher = more fragmented.",
    )
    top[3].metric(
        "MSA",
        f"{(metrics.msa or 0.0):.2f}",
        help="Mean Species Abundance (2015 GLOBIO baseline).",
    )
    top[4].metric(
        "B-Score",
        f"{(metrics.bscore or 0.0):.1f}",
        help="Composite biodiversity score (0–100) based on structural and diversity metrics.",
    )

    bottom = st.columns(6)

    bottom[0].metric(
        "NDVI μ",
        f"{(metrics.ndvi_mean or 0.0):.2f}",
        help="Average NDVI value; higher indicates denser/healthier vegetation.",
    )
    bottom[1].metric(
        "MSAVI μ",
        f"{(metrics.msavi_mean or 0.0):.2f}",
        help="Average MSAVI value; soil-adjusted vegetation index useful for sparse vegetation.",
    )

    bottom[2].metric(
        "NDVI slope",
        f"{(metrics.ndvi_slope or 0.0):.3f}",
        help="Annual NDVI trend; positive = increasing greenness.",
    )
    bottom[3].metric(
        "ΔNDVI",
        f"{(metrics.ndvi_delta or 0.0):.3f}",
        help="Change in NDVI between baseline and last year.",
    )
    bottom[4].metric(
        "NDVI p-value",
        f"{(metrics.ndvi_p_value or 0.0):.3f}",
        help="Mann–Kendall p-value for NDVI trend.",
    )
    bottom[5].metric(
        "% valid obs",
        f"{(metrics.valid_obs_pct or 0.0):.1f}",
        help="Percentage of valid observations in NDVI time series.",
    )


def _bscore_band(score: float) -> tuple[str, str]:
    """Return risk label and emoji for B-Score band."""
    if score < 40:
        return ("High risk", "🟥")
    elif score < 70:
        return ("Moderate risk", "🟧")
    else:
        return ("Low risk", "🟩")


def bscore_gauge(
    score: float,
    *,
    title: Optional[str] = None,
    weights: Optional[dict[str, float]] = None,
) -> None:
    """Display a gauge chart for the B-Score, with risk band and formula explanation."""
    # Define default weights
    default_weights: dict[str, float] = {
        "intactness": 0.4,
        "shannon": 0.3,
        "fragmentation": 0.3,
    }
    used_weights = weights if weights is not None else default_weights

    # Colored gauge steps for risk bands
    steps = [
        {"range": [0, 40], "color": "#f7b6b2"},  # Red-tint
        {"range": [40, 70], "color": "#ffd480"},  # Amber-tint
        {"range": [70, 100], "color": "#b7e5c8"},  # Green-tint
    ]

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": ""},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#159466"},
                "bgcolor": "white",
                "steps": steps,
                "threshold": {
                    "line": {"color": "#159466", "width": 4},
                    "thickness": 0.75,
                    "value": score,
                },
            },
            title={"text": title or "Project B-Score"},
        )
    )
    fig.update_layout(height=200, margin=dict(l=15, r=27, t=40, b=10))

    with st.container(height=450):
        st.plotly_chart(fig, use_container_width=True)

        # Show risk band label and emoji
        band_label, band_emoji = _bscore_band(score)
        st.caption(f"{band_emoji} **{band_label}** (B-Score = {score:.1f})")

        # Show weights used
        w_str = ", ".join(f"{k}: {v:.2f}" for k, v in used_weights.items())
        st.caption(f"**B-Score weights:** {w_str}")

        # Expander for explanation
        with st.expander("How we calculate B-Score"):
            st.markdown(
                """
                The **B-Score** is a composite index designed to summarize key biodiversity indicators into a single value between 0 (worst) and 100 (best).

                **General formula:**
                ```
                B-Score = w₁ × Intactness + w₂ × Shannon + w₃ × (1 - Fragmentation)
                ```
                where *w₁*, *w₂*, and *w₃* are the weights assigned to each metric (see above), and all input metrics are normalized to [0, 1] before weighting.

                **Sources:**  
                - Intactness: Proportion of native vegetation remaining  
                - Shannon: Landscape diversity (Shannon index)  
                - Fragmentation: Degree of habitat fragmentation (normalized)

                **Limitations:**  
                - The B-Score simplifies complex ecological data into a single metric and may not capture all aspects of biodiversity.  
                - Weightings and formulas are subject to expert judgment and may not be universally applicable.
                """
            )
