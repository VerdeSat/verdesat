"""
Module `ingestion.sensorspec` defines the SensorSpec class, which encapsulates
sensor metadata (band mappings, resolutions, and mask strategies) and provides
cloud masking and spectral index computation.
"""

import json
from pathlib import Path
from typing import Optional
import ee
from .indices import compute_index


class SensorSpec:
    """
    Holds metadata for a sensor (bands, collection ID, etc).
    """

    _registry: Optional[dict] = None

    def __init__(
        self,
        collection_id: str,
        bands: dict,
        native_resolution: int,
        cloud_mask_method: str,
        fmask_exclude: list[int] | None = None,
        scl_exclude: list[int] | None = None,
    ):
        self.collection_id = collection_id
        self.bands = bands
        self.native_resolution = native_resolution
        self.cloud_mask_method = cloud_mask_method
        # Bits to exclude in Fmask (e.g., FILL, WATER, SHADOW, SNOW, CLOUD)
        self.fmask_exclude = fmask_exclude or [1, 2, 4, 8, 16]
        # Codes to exclude based on Scene Classification Layer for Sentinel-2
        self.scl_exclude = scl_exclude or []

    def cloud_mask(self, img: ee.Image) -> ee.Image:
        """
        Apply cloud mask based on this sensor's cloud_mask_method.
        Supports 'fmask'; other methods can be added.
        """
        method = self.cloud_mask_method.lower()
        if method == "fmask":
            exclude_mask = sum(self.fmask_exclude)
            fmask_band = self.bands["qa"]
            fmask = img.select(fmask_band)
            valid = fmask.bitwiseAnd(exclude_mask).eq(0)
            return img.updateMask(valid)
        elif method == "s2_scl":
            # Exclude pixels with SCL codes in scl_exclude
            scl_band = self.bands["scl"]
            scl = img.select(scl_band)
            mask = None
            for code in self.scl_exclude:
                cond = scl.neq(code)
                mask = cond if mask is None else mask.And(cond)
            return img.updateMask(mask)
        # No masking for other methods by default
        return img

    def compute_index(self, img: ee.Image, index_name: str) -> ee.Image:
        """
        Compute a spectral index on the given EE Image using this sensor's band aliases.
        """
        # Rename bands to standard aliases (e.g., 'nir','red','blue', etc.)
        alias_img = img.select(list(self.bands.values()), list(self.bands.keys()))
        # Delegate to generic compute_index on alias image
        return compute_index(alias_img, index_name)

    @classmethod
    def _load_registry(cls) -> dict:
        """Load sensor specs from resources/sensor_specs.json."""
        if cls._registry is None:
            # Path to resource file
            base = Path(__file__).resolve().parent.parent
            spec_file = base / "resources" / "sensor_specs.json"
            with open(spec_file, "r", encoding="utf-8") as f:
                cls._registry = json.load(f)
        return cls._registry

    @classmethod
    def from_collection_id(cls, collection_id: str) -> "SensorSpec":
        """
        Factory method: create a SensorSpec from a collection ID by reading the registry.
        """
        registry = cls._load_registry()
        spec = registry.get(collection_id)
        if spec is None:
            raise ValueError(
                f"Collection ID '{collection_id}' not found in sensor_specs.json"
            )
        return cls(
            collection_id=collection_id,
            bands=spec["bands"],
            native_resolution=spec["native_resolution"],
            cloud_mask_method=spec["cloud_mask_method"],
            fmask_exclude=spec.get("fmask_exclude"),
            scl_exclude=spec.get("scl_exclude"),
        )
