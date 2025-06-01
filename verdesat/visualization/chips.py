import os
import logging
import requests
from typing import (
    List,
    Optional,
    Union,
    Dict,
    Any,
)

import ee
from ee import EEException

from verdesat.ingestion.eemanager import EarthEngineManager
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.ingestion.indices import compute_index
from verdesat.analytics.engine import AnalyticsEngine
from verdesat.geo.utils import buffer_geometry

logger = logging.getLogger(__name__)


class ChipExporter:
    """
    Responsible for taking a single ee.Image (a composite) and exporting
    it—per‐feature—to disk as either PNG thumbnails or GeoTIFFs (optionally
    converting them to COG).
    """

    def __init__(self, out_dir: str, fmt: str) -> None:
        """
        :param out_dir: directory where chips will be written
        :param fmt: 'png' or 'geotiff'
        """
        self.out_dir = out_dir
        self.fmt = fmt.lower()
        os.makedirs(self.out_dir, exist_ok=True)

    def _build_viz_params(
        self,
        bands: List[str],
        min_val: Union[float, List[float]],
        max_val: Union[float, List[float]],
        scale: int,
        palette: Optional[List[str]],
        gamma: Optional[float],
        dims: int = 512,
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
            params["dimensions"] = 512  # dims is always 512 for PNG
            if palette is not None and gamma is None:
                params["palette"] = palette
            elif palette is not None and gamma is not None:
                logger.warning("Palette ignored because gamma correction is enabled")
        else:
            # non‐PNG (GeoTIFF): specify format
            params["format"] = "GEOTIFF"

        return params

    def _convert_to_cog(self, path: str) -> None:
        """
        Convert a just‐written GeoTIFF into a Cloud‐Optimized GeoTIFF (COG).
        If conversion fails, issue a warning.
        """
        try:
            import rasterio
            from rasterio.enums import Resampling
        except ImportError:
            logger.warning(
                "rasterio not installed; skipping COG conversion for %s", path
            )
            return

        try:
            with rasterio.open(path) as src:
                profile = src.profile
                data = src.read()

            profile.update(
                driver="GTiff",
                compress="deflate",
                tiled=True,
                blockxsize=512,
                blockysize=512,
            )

            with rasterio.open(path, "w", **profile) as dst:
                dst.write(data)
                dst.build_overviews([2, 4, 8, 16], Resampling.nearest)
                dst.update_tags(OVR_RESAMPLING="NEAREST")

            logger.info("✔ Converted to COG: %s", path)
        except Exception as cog_err:
            logger.warning("⚠ COG conversion failed for %s: %s", path, cog_err)

    def export_one(
        self,
        img: ee.Image,
        feature: Dict[str, Any],
        date_str: str,
        bands: List[str],
        palette: Optional[List[str]],
        scale: int,
        buffer_m: float,
        gamma: Optional[float],
        min_val: Union[float, List[float]],
        max_val: Union[float, List[float]],
    ) -> None:
        """
        Export **one** composite (ee.Image) for **one** feature.

        Steps:
          1) Clip the image by feature geometry + buffer
          2) Compute bounding box for 'region'
          3) Build viz‐params dict (fixed dims=512 for PNG)
          4) Retrieve thumbnail or download URL
          5) Download via HTTP and write to disk
          6) If GeoTIFF, convert to COG
        """
        # 1) Assemble the buffered geometry
        geom_json = feature.get("geometry")
        feat_props = feature.get("properties", {})
        pid = feat_props.get("id") or feat_props.get("system:index")
        if pid is None:
            pid = "unknown"

        try:
            # Convert geojson dict → ee.Geometry, then buffer
            geom = ee.Geometry(geom_json)
            if buffer_m > 0:
                geom = geom.buffer(buffer_m)
        except Exception as e:
            logger.error("Failed to construct ee.Geometry for feature %s: %s", pid, e)
            return

        clipped = img.clip(geom)

        # 2) Compute bounding box for 'region'
        try:
            bbox_info = ee.FeatureCollection([feature]).geometry().bounds().getInfo()
            coords = bbox_info.get("coordinates", [[]])[0]
            xs = [pt[0] for pt in coords]
            ys = [pt[1] for pt in coords]
            region_bbox = [min(xs), min(ys), max(xs), max(ys)]
        except Exception as e:
            logger.warning("Could not compute bbox for feature %s: %s", pid, e)
            return

        # 3) Build viz params (dims=512 for PNG)
        viz_params = self._build_viz_params(
            bands=bands,
            min_val=min_val,
            max_val=max_val,
            scale=scale,
            palette=palette,
            gamma=gamma,
        )
        # Add region explicitly (old logic: build dims then region)
        viz_params["region"] = region_bbox

        # 4) Build URL
        try:
            if self.fmt == "png":
                url = clipped.getThumbURL(viz_params)
                ext = "png"
            else:
                url = clipped.getDownloadURL(viz_params)
                ext = "tiff"
        except EEException as ee_err:
            logger.error("Failed to get URL for %s on %s: %s", pid, date_str, ee_err)
            return

        # 5) Download via HTTP
        com_type = "NDVI" if "NDVI" in bands else "RGB"
        filename = f"{com_type}_{pid}_{date_str}.{ext}"  # ← original pattern
        out_path = os.path.join(self.out_dir, filename)
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            with open(out_path, "wb") as fh:
                fh.write(resp.content)
            logger.info("✔ Wrote %s file: %s", ext, out_path)
        except Exception as dl_err:
            logger.error(
                "Failed to download %s for %s on %s: %s", ext, pid, date_str, dl_err
            )
            return

        # 6) If GeoTIFF, convert to COG
        if ext != "png":
            self._convert_to_cog(out_path)


class ChipService:
    """
    Orchestrates end‐to‐end chip creation:
      1) Initialize EE
      2) Fetch raw ImageCollection via EarthEngineManager
      3) (Optional) map compute_index(based on index_formulas.json)
      4) Build composites via AnalyticsEngine
      5) For each composite & each feature, call ChipExporter.export_one()
    """

    def __init__(self, ee_manager: EarthEngineManager, sensor_spec: SensorSpec) -> None:
        self.ee_manager = ee_manager
        self.sensor_spec = sensor_spec

    def run(
        self,
        geojson: Dict[str, Any],
        collection_id: str,
        start: str,
        end: str,
        period: str,
        chip_type: str,
        scale: int,
        min_val: Optional[float],
        max_val: Optional[float],
        buffer: int,
        buffer_percent: Optional[float],
        gamma: Optional[float],
        percentile_low: Optional[float],
        percentile_high: Optional[float],
        palette: Optional[List[str]],
        fmt: str,
        out_dir: str,
        mask_clouds: bool,
    ) -> None:
        """
        Main entrypoint.

        :param geojson: loaded GeoJSON dict (with "features" list)
        :param collection_id: Earth Engine collection string (e.g. 'NASA/HLS/HLSL30/v002')
        :param start: 'YYYY-MM-DD'
        :param end:   'YYYY-MM-DD'
        :param period: 'M' or 'Y'
        :param chip_type: 'truecolor' or the name of any index present in index_formulas.json
        :param scale: resolution in meters
        :param min_val, max_val: explicit min/max; if None, defaults will be used
        :param buffer: integer meters
        :param buffer_percent: float percentage of AOI extent
        :param gamma: gamma correction
        :param percentile_low/high: for auto‐stretch (unused here)
        :param palette: list of hex/RGB strings (only used by indices, e.g. NDVI)
        :param fmt: 'png' or 'geotiff'
        :param out_dir: where to save files
        :param mask_clouds: whether to call mask_fmask_bits in get_image_collection
        """
        # 1) Initialize EE
        self.ee_manager.initialize()

        # 2) Ensure GeoJSON has a non‐empty features list
        features = geojson.get("features", [])
        if not isinstance(features, list) or len(features) == 0:
            raise ValueError("GeoJSON must have a non‐empty 'features' list")
        ee_fc = ee.FeatureCollection(geojson)

        # 3) Fetch raw ImageCollection
        raw_coll = self.ee_manager.get_image_collection(
            collection_id, start, end, ee_fc, mask_clouds=mask_clouds
        )

        # 4) If chip_type != 'truecolor', treat as index—but first alias raw bands via SensorSpec
        bands: List[str]
        if chip_type.lower() != "truecolor":
            bands = [chip_type.upper()]
            raw_coll = raw_coll.map(
                lambda img: (
                    self.sensor_spec.compute_index(img, chip_type.lower())
                    .rename(chip_type.upper())
                    .copyProperties(img, ["system:time_start"])
                )
            )
        else:
            bands = ["B4", "B3", "B2"]  # truecolor → RGB

        # 5) Determine default min/max if not provided
        if min_val is None or max_val is None:
            if chip_type.lower() != "truecolor":
                default_min, default_max = 0.0, 1.0
            else:
                default_min, default_max = 0.0, 0.4
            min_val = min_val if min_val is not None else default_min
            max_val = max_val if max_val is not None else default_max

        # 6) Build composites (monthly/yearly mean)
        composites = AnalyticsEngine.build_composites(
            base_ic=raw_coll,
            period=period,
            reducer=ee.Reducer.mean(),
            start=start,
            end=end,
            bands=bands,
            scale=scale,
        )

        # 7) Instantiate exporter
        exporter = ChipExporter(out_dir=out_dir, fmt=fmt)

        # 8) Loop over composites → list, then per‐feature
        total_count = int(composites.size().getInfo())
        if total_count <= 0:
            raise RuntimeError("No composites generated (empty EE collection)")

        image_list = composites.toList(total_count)
        for i in range(total_count):
            try:
                img = ee.Image(image_list.get(i))
                date_str: str = (
                    ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
                )

                for feat in features:
                    # 9) Compute buffer in metres for this feature
                    buffer_m = buffer_geometry(feat, buffer, buffer_percent)

                    exporter.export_one(
                        img=img,
                        feature=feat,
                        date_str=date_str,
                        bands=bands,
                        palette=palette,
                        scale=scale,
                        buffer_m=buffer_m,
                        gamma=gamma,
                        min_val=min_val,
                        max_val=max_val,
                    )
            except Exception as e:
                logger.error("Failed exporting composite #%d: %s", i, e, exc_info=True)
                continue

        logger.info("Finished exporting all chips to %s", out_dir)
