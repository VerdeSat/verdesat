from __future__ import annotations

"""Composite biodiversity score calculator."""

from dataclasses import dataclass
from pathlib import Path
import yaml

from .metrics import MetricsResult


@dataclass
class WeightsConfig:
    """Weights for each biodiversity metric."""

    intactness: float = 1.0
    shannon: float = 1.0
    fragmentation: float = 1.0

    @classmethod
    def from_yaml(cls, path: str | Path) -> "WeightsConfig":
        """Load weights from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            intactness=float(data.get("intactness", 1.0)),
            shannon=float(data.get("shannon", 1.0)),
            fragmentation=float(data.get("fragmentation", 1.0)),
        )


DEFAULT_WEIGHTS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "bscore_weights.yaml"
)


class BScoreCalculator:
    """Compute a composite biodiversity score (0-100)."""

    def __init__(self, weights: WeightsConfig | None = None) -> None:
        self.weights = weights or WeightsConfig.from_yaml(DEFAULT_WEIGHTS_PATH)

    def score(self, metrics: MetricsResult) -> float:
        """Return the weighted B-Score as a value between 0 and 100."""
        w = self.weights
        total_w = w.intactness + w.shannon + w.fragmentation
        if total_w == 0:
            return 0.0
        value = (
            w.intactness * metrics.intactness
            + w.shannon * metrics.shannon
            + w.fragmentation * (1 - metrics.fragmentation.normalised_density)
        )
        return float(100.0 * value / total_w)
