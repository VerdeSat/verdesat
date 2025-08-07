"""Project models for managing client projects and their AOIs."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Literal

from verdesat.analytics.timeseries import TimeSeries
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import StorageAdapter
from verdesat.geo.aoi import AOI
from verdesat.ingestion import create_ingestor
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.ingestion.vector_preprocessor import VectorPreprocessor
from verdesat.visualization.visualizer import Visualizer


@dataclass
class Project:
    """Lightweight project model holding AOIs and related artefacts."""

    name: str
    customer: str
    aois: List[AOI]
    config: ConfigManager
    storage: StorageAdapter | None = None
    logger: logging.Logger = field(default_factory=lambda: Logger.get_logger(__name__))
    rasters: Dict[str, Dict[str, str]] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_geojson(
        cls,
        name: str,
        customer: str,
        geojson: Dict[str, Any],
        config: ConfigManager,
        *,
        storage: StorageAdapter | None = None,
        logger: logging.Logger | None = None,
    ) -> "Project":
        """Construct a project from a GeoJSON feature collection."""

        log = logger or Logger.get_logger(__name__)
        id_col = config.get("id_col", "id")
        aois = AOI.from_geojson(geojson, id_col=id_col)
        log.debug("Loaded %s AOIs from GeoJSON", len(aois))
        return cls(
            name=name,
            customer=customer,
            aois=aois,
            config=config,
            storage=storage,
            logger=log,
        )

    def attach_rasters(
        self,
        ndvi_paths: Dict[str, str],
        msavi_paths: Dict[str, str],
    ) -> None:
        """Attach NDVI and MSAVI rasters to AOIs by their identifier."""
        self.logger.debug(
            "Attaching rasters: %s NDVI, %s MSAVI", len(ndvi_paths), len(msavi_paths)
        )
        id_col = self.config.get("id_col", "id")
        for aoi in self.aois:
            aoi_id = str(aoi.static_props.get(id_col))
            entry = self.rasters.setdefault(aoi_id, {})
            if aoi_id in ndvi_paths:
                entry["ndvi"] = ndvi_paths[aoi_id]
            if aoi_id in msavi_paths:
                entry["msavi"] = msavi_paths[aoi_id]

    def attach_metrics(self, metrics: Dict[str, Any]) -> None:
        """Store computed metrics for the project."""
        self.logger.debug("Attaching metrics: %s", list(metrics.keys()))
        self.metrics.update(metrics)

    def add_aoi(self, aoi: AOI) -> None:
        """Add a new AOI to the project."""
        self.aois.append(aoi)

    @classmethod
    def from_directory(
        cls, name: str, customer: str, input_dir: str, config: ConfigManager
    ) -> "Project":
        """Factory: build a project by preprocessing vector inputs into AOIs."""
        vp = VectorPreprocessor(input_dir)
        gdf = vp.run()
        aois = AOI.from_gdf(gdf, id_col=config.get("id_col", "id"))
        return cls(name, customer, aois, config)

    def run_pipeline(
        self,
        collection_id: str,
        index: str,
        start_date: str,
        end_date: str,
        scale: int,
        output_dir: str,
        freq: Literal["D", "ME", "YE"] = "YE",
        report_title: str | None = None,
    ) -> None:
        """Execute the full workflow: download timeseries, attach to AOIs, and generate a report."""

        sensor = SensorSpec.from_collection_id(collection_id)
        backend = self.config.get("ingestor_backend", "ee")
        ingestor = create_ingestor(backend, sensor)
        value_col = self.config.get_value_col(index)

        for aoi in self.aois:
            df = ingestor.download_timeseries(
                aoi,
                start_date,
                end_date,
                scale,
                index,
                value_col,
                chunk_freq="YE",
                freq=freq,
            )
            ts = TimeSeries.from_dataframe(df, index=index)
            aoi.add_timeseries(index, ts)

        viz = Visualizer()
        title = report_title or self.config.get("report_title", "VerdeSat Report")
        viz.generate_report(output_dir, title=title)
