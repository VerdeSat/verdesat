"""Module implementing ChipExporter and ChipService for exporting image chips via GEE."""

import os
from typing import Any, Dict, List, Optional, Union

import ee
import requests
from ee import EEException

from verdesat.services.raster_utils import convert_to_cog

from verdesat.analytics.engine import AnalyticsEngine
from verdesat.geo.aoi import AOI
from verdesat.ingestion.eemanager import EarthEngineManager
from verdesat.ingestion.indices import INDEX_REGISTRY
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.visualization._chips_config import ChipsConfig
from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS, StorageAdapter


class ChipExporter:
    """
    Responsible for taking a single ee.Image (a composite) and exporting
    it—per‐feature—to disk as either PNG thumbnails or GeoTIFFs (optionally
    converting them to COG).
    """

    def __init__(
        self,
        ee_manager: EarthEngineManager,
        out_dir: str,
        fmt: str,
        storage: StorageAdapter | None = None,
        logger=None,
    ) -> None:
        """
        :param ee_manager: EarthEngineManager instance
        :param out_dir: directory where chips will be written
        :param fmt: 'png' or 'geotiff'
        """
        self.ee_manager = ee_manager
        self.out_dir = out_dir
        self.fmt = fmt.lower()
        self.storage = storage or LocalFS()
        self.logger = logger or Logger.get_logger(__name__)

    def _build_viz_params(
        self,
        bands: List[str],
        min_val: Union[float, List[float]],
        max_val: Union[float, List[float]],
        scale: int,
        palette: Optional[tuple[str, ...]],
        gamma: Optional[float],
    ) -> Dict[str, Any]:
        """
        Construct the Earth Engine visualization parameters dict for a single image.
        Matches the original `build_viz_params` logic: fixed dimensions for PNG.
        """
        params: Dict[str, Any] = {
            "bands": bands,
            "min": min_val,
            "max": max_val,
            "scale": scale,
        }

        if gamma is not None:
            params["gamma"] = [gamma] * len(bands)

        if self.fmt == "png":
            # For PNG, drop 'scale' and force dims=512 (old behavior)
            params.pop("scale", None)
            params["dimensions"] = 512
            if palette is not None and len(bands) == 1 and gamma is None:
                params["palette"] = palette
            elif palette is not None and len(bands) > 1:
                self.logger.warning("Palette ignored when visualizing multiple bands")
            elif palette is not None and gamma is not None:
                self.logger.warning(
                    "Palette ignored because gamma correction is enabled"
                )
        else:
            # non‐PNG (GeoTIFF): specify format
            params["format"] = "GEOTIFF"

        return params

    def export_one(
        self,
        img: ee.Image,
        aoi: AOI,
        date_str: str,
        com_type: str,
        bands: List[str],
        palette: Optional[tuple[str, ...] | None],
        scale: int,
        buffer_m: float,
        gamma: Optional[float],
        min_val: Union[float, List[float]],
        max_val: Union[float, List[float]],
    ) -> str | None:
        """Export a single composite for one AOI and return the output URI.

        Steps:
          1) Clip the image by feature geometry + buffer
          2) Compute bounding box for ``region``
          3) Build visualization parameters
          4) Retrieve thumbnail or download URL
          5) Download via HTTP and persist through the storage adapter
          6) If GeoTIFF, convert to Cloud Optimized GeoTIFF

        Returns
        -------
        str | None
            Destination URI if successful, otherwise ``None``.
        """
        pid = aoi.static_props.get("id") or aoi.static_props.get(
            "system:index", "unknown"
        )

        try:
            geom = aoi.buffered_ee_geometry(buffer_m)
        except (EEException, ValueError) as e:
            self.logger.error("Failed to construct ee.Geometry for AOI %s: %s", pid, e)
            return None

        clipped = img.clip(geom)

        try:
            bbox_info = self.ee_manager.safe_get_info(geom.bounds()) or {}
            coords = bbox_info.get("coordinates", [[]])[0]
            xs = [pt[0] for pt in coords]
            ys = [pt[1] for pt in coords]
            region_bbox = [min(xs), min(ys), max(xs), max(ys)]
        except EEException as ee_err:
            self.logger.warning("Could not compute bbox for AOI %s: %s", pid, ee_err)
            return None
        except KeyError as key_err:
            self.logger.warning("BBox info missing keys for AOI %s: %s", pid, key_err)
            return None

        viz_params = self._build_viz_params(
            bands=bands,
            min_val=min_val,
            max_val=max_val,
            scale=scale,
            palette=palette,
            gamma=gamma,
        )
        viz_params["region"] = region_bbox

        try:
            if self.fmt == "png":
                url = clipped.getThumbURL(viz_params)
                ext = "png"
            else:
                url = clipped.getDownloadURL(viz_params)
                ext = "tif"
        except EEException as ee_err:
            self.logger.error(
                "Failed to get URL for %s on %s: %s", pid, date_str, ee_err
            )
            return None

        filename = f"{com_type}_{pid}_{date_str}.{ext}"
        out_path = self.storage.join(self.out_dir, filename)

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            self.storage.write_bytes(out_path, resp.content)
            self.logger.info("✔ Wrote %s file: %s", ext, out_path)
        except requests.RequestException as dl_err:
            self.logger.error(
                "Failed to download %s for %s on %s: %s", ext, pid, date_str, dl_err
            )
            return None

        if ext != "png":
            convert_to_cog(
                out_path,
                storage=self.storage,
                geometry=aoi.geometry,
                logger=self.logger,
            )

        return out_path


class ChipService:
    """
    Orchestrates end‐to‐end chip creation:
      1) Initialize EE
      2) Fetch raw ImageCollection via EarthEngineManager
      3) (Optional) map compute_index(based on index_formulas.json)
      4) Build composites via AnalyticsEngine
      5) For each composite & each feature, call ChipExporter.export_one()
    """

    def __init__(
        self,
        ee_manager: EarthEngineManager,
        sensor_spec: SensorSpec,
        storage: StorageAdapter | None = None,
        logger=None,
    ) -> None:
        self.ee_manager = ee_manager
        self.sensor_spec = sensor_spec
        self.storage = storage or LocalFS()
        self.logger = logger or Logger.get_logger(__name__)

    def run(self, aois: List[AOI], config: ChipsConfig) -> None:
        """
        Main entry‑point executed by the CLI.

        Parameters
        ----------
        aois : List[AOI]
            List of pre‑constructed AOI objects to export chips for.
        config : ChipsConfig
            Immutable configuration object carrying every parameter required
            for chip generation (see `chips_config.py`).
        """
        features: List[Dict[str, Any]] = []
        for aoi in aois:
            feat = {
                "type": "Feature",
                "geometry": aoi.geometry.__geo_interface__,
                "properties": {**aoi.static_props},
            }
            features.append(feat)

        if not features:
            raise ValueError("AOI list is empty; nothing to export")

        ee_fc = ee.FeatureCollection(
            {"type": "FeatureCollection", "features": features}
        )

        chip_key = config.chip_type.lower()
        com_type = chip_key.upper().replace(",", "_")

        raw_coll = self.ee_manager.get_image_collection(
            config.collection_id,
            config.start,
            config.end,
            ee_fc,
            mask_clouds=config.mask_clouds,
        )

        if chip_key in INDEX_REGISTRY:
            bands = [chip_key.upper()]
            raw_coll = raw_coll.map(
                lambda img: (
                    self.sensor_spec.compute_index(img, chip_key)
                    .rename(chip_key.upper())
                    .copyProperties(img, ["system:time_start"])
                )
            )
        else:
            aliases = [alias.strip().lower() for alias in chip_key.split(",")]
            invalid = [a for a in aliases if a not in self.sensor_spec.bands]
            if invalid:
                raise ValueError(f"Unknown band alias(es): {invalid}")
            actual_bands = [self.sensor_spec.bands[a] for a in aliases]
            bands = actual_bands
            raw_coll = raw_coll.select(actual_bands)

        if config.min_val is None or config.max_val is None:
            if chip_key in INDEX_REGISTRY:
                default_min, default_max = 0.0, 1.0
            else:
                default_min, default_max = 0.0, 0.4
            min_val = config.min_val if config.min_val is not None else default_min
            max_val = config.max_val if config.max_val is not None else default_max
        else:
            min_val = config.min_val
            max_val = config.max_val

        composites = AnalyticsEngine.build_composites(
            base_ic=raw_coll,
            period=config.period,
            reducer=ee.Reducer.mean(),
            start=config.start,
            end=config.end,
            bands=bands,
            scale=config.scale,
        )

        exporter = ChipExporter(
            ee_manager=self.ee_manager,
            out_dir=config.out_dir,
            fmt=config.fmt,
            storage=self.storage,
        )

        raw_count = self.ee_manager.safe_get_info(composites.size())
        total_count = int(raw_count or 0)
        if total_count <= 0:
            raise RuntimeError("No composites generated (empty EE collection)")

        image_list = composites.toList(total_count)
        for i in range(total_count):
            try:
                img = ee.Image(image_list.get(i))
                date_obj = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
                date_str = self.ee_manager.safe_get_info(date_obj)

                for aoi in aois:
                    buffer_m = config.buffer
                    exporter.export_one(  # noqa: E501
                        img=img,
                        aoi=aoi,
                        date_str=date_str,
                        com_type=com_type,
                        bands=bands,
                        palette=config.palette,
                        scale=config.scale,
                        buffer_m=buffer_m,
                        gamma=config.gamma,
                        min_val=min_val,
                        max_val=max_val,
                    )
            except EEException as ee_err:
                self.logger.error(
                    "Failed exporting composite #%d due to EE error: %s",
                    i,
                    ee_err,
                    exc_info=True,
                )
                continue

        self.logger.info("Finished exporting all chips to %s", config.out_dir)
