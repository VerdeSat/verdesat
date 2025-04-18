from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

def landcover_classifier():
    """
    Simple RF pipeline: scaling + random forest.
    Extend with feature selection or PCA later.
    """
    return Pipeline([
        ('scaler', StandardScaler()),
        ('rf', RandomForestClassifier(n_estimators=100))
    ])

def forecasting_pipeline():
    """
    Placeholder for time‑series forecasting (Prophet / LSTM / XGBoost).
    Wrap in scikit‑learn API for uniformity.
    """
    raise NotImplementedError