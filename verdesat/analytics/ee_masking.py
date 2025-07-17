from __future__ import annotations

"""Utilities for applying cloud masks to ImageCollections."""

from ee import ImageCollection

from verdesat.ingestion.sensorspec import SensorSpec


def mask_collection(collection: ImageCollection, sensor: SensorSpec) -> ImageCollection:
    """Apply the sensor-specific cloud mask to each image in the collection."""
    return collection.map(sensor.cloud_mask)
