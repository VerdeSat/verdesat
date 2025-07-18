import pandas as pd
import statsmodels.api as sm
from typing import Literal

from .results import TrendResult


from verdesat.core.config import ConfigManager


def compute_trend(
    df: pd.DataFrame,
    column: str = ConfigManager.VALUE_COL_TEMPLATE.format(
        index=ConfigManager.DEFAULT_INDEX
    ),
    id_col: str = "id",
) -> TrendResult:
    """Fit a linear trend to each polygon's time series and return a :class:`TrendResult`."""
    rows = []
    for pid, grp in df.groupby(id_col):
        # Drop missing
        s = grp.dropna(subset=[column])
        if s.empty:
            continue
        # ordinal X
        X = sm.add_constant(s["date"].map(pd.Timestamp.toordinal))
        y = s[column]
        model = sm.OLS(y, X).fit()
        fitted = model.predict(X)
        temp = pd.DataFrame({"id": pid, "date": s["date"], "trend": fitted})
        rows.append(temp)
    result_df = pd.concat(rows, ignore_index=True)
    return TrendResult(result_df)
