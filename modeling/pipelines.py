from sklearn.pipeline import Pipeline  # type: ignore[import]
from sklearn.ensemble import RandomForestClassifier  # type: ignore[import]
from sklearn.preprocessing import StandardScaler  # type: ignore[import]


def landcover_classifier():
    """
    Simple RF pipeline: scaling + random forest.
    Extend with feature selection or PCA later.
    """
    return Pipeline(
        [("scaler", StandardScaler()), ("rf", RandomForestClassifier(n_estimators=100))]
    )


def forecasting_pipeline():
    """
    Placeholder for time‑series forecasting (Prophet / LSTM / XGBoost).
    Wrap in scikit‑learn API for uniformity.
    """
    raise NotImplementedError
