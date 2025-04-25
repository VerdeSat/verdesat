import os
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import DecomposeResult
import pandas as pd


def plot_time_series(
    df: pd.DataFrame, index_col: str, output_path: str, agg_freq: str = "D"
) -> None:
    """
    Plot raw or aggregated time series for each polygon and save as PNG.

    Args:
        df: DataFrame with columns ['id','date', index_col]
        index_col: name of the column to plot (e.g., 'mean_ndvi')
        output_path: file path for the output PNG
        agg_freq: aggregation frequency: 'D', 'M', or 'Y'
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

    plt.figure(figsize=(10, 5))
    for pid, group in df.groupby("id"):
        plt.plot(group["date"], group[index_col], marker="o", label=f"Polygon {pid}")
    plt.xlabel("Date")
    plt.ylabel(index_col)
    plt.title(f"{index_col} Time Series ({agg_freq})")
    plt.legend()
    plt.grid(True)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_decomposition(result: DecomposeResult, output_path: str) -> None:
    """
    Save seasonal decomposition components (observed, trend, seasonal, resid) as a PNG.

    Args:
        result: statsmodels DecomposeResult object
        output_path: file path for the output PNG
    """
    fig = result.plot()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
