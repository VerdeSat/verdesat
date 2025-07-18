"""Ingestion package with backend factory."""

from .base import BaseDataIngestor
from .earthengine_ingestor import EarthEngineIngestor
from .sensorspec import SensorSpec


def create_ingestor(backend: str, sensor: SensorSpec, **kwargs) -> BaseDataIngestor:
    """Factory returning an ingestor instance based on backend name."""
    name = backend.lower()
    if name in {"ee", "earthengine"}:
        return EarthEngineIngestor(sensor, **kwargs)
    raise ValueError(f"Unknown ingestor backend '{backend}'")


__all__ = ["BaseDataIngestor", "EarthEngineIngestor", "create_ingestor"]
