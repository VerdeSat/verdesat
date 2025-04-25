import os
import plotly.express as px
from typing import Optional
import pandas as pd


def plot_timeseries_html(
    df: pd.DataFrame, index_col: str, output_path: str, agg_freq: Optional[str] = None
) -> None:
    """
    Create an interactive HTML time‐series plot.

    Args:
      df: DataFrame with columns ['id','date', index_col]
      index_col: the column to plot (e.g. 'mean_ndvi')
      output_path: path for the output .html
      agg_freq: Optional resampling rule ('D','M','Y'). If provided,
        df is aggregated by this freq before plotting.
    """
    # Optionally aggregate
    if agg_freq and agg_freq != "D":
        df = (
            df.set_index("date")
            .groupby("id")[index_col]
            .resample(agg_freq)
            .mean()
            .reset_index()
        )

    fig = px.line(
        df,
        x="date",
        y=index_col,
        color="id",
        title=f"Interactive {index_col.capitalize()} Time Series",
        labels={index_col: index_col, "date": "Date", "id": "Polygon ID"},
        markers=True,
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")
