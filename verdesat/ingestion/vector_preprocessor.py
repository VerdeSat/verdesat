"""
Module `ingestion.vector_preprocessor` defines the VectorPreprocessor class,
which processes a directory of vector files into a cleaned GeoDataFrame.
"""

import os
import zipfile
import tempfile

import pandas as pd
import geopandas as gpd
from shapely import wkb

from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger


class VectorPreprocessor:
    """
    Processes vector files in a directory and returns a cleaned GeoDataFrame.

    Steps:
      - Collect supported files (recursive)
      - Read & reproject to EPSG:4326 (or configured CRS)
      - Repair geometries, explode multipart, drop invalids
      - Ensure sequential ID column
      - Calculate area in m2 (using configured area_crs, default EPSG:8857)
      - Add 'username' from directory basename
      - Drop Z dimension from geometries
    """

    def __init__(
        self,
        input_dir: str,
        exts: list[str] | None = None,
        target_crs: str = "EPSG:4326",
        area_crs: int = 8857,
        id_col: str = "id",
        logger=None,
    ):
        self.input_dir = input_dir
        self.exts = exts or [e.lower() for e in ConfigManager.SUPPORTED_INPUT_FORMATS]
        self.target_crs = target_crs
        self.area_crs = area_crs
        self.id_col = id_col
        self.gdf: gpd.GeoDataFrame | None = None
        self.logger = logger or Logger.get_logger(__name__)

    def collect_files(self) -> list[str]:
        """Gather all supported vector files in the directory (recursive)."""
        paths: list[str] = []
        for root, _, files in os.walk(self.input_dir):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in self.exts:
                    paths.append(os.path.join(root, fname))
        return paths

    def _read_file(self, filepath: str) -> gpd.GeoDataFrame:
        """Read a single file, handling KMZ/KML if needed."""
        if filepath.lower().endswith(".kmz"):
            gdfs = []
            with zipfile.ZipFile(filepath, "r") as z:
                kmls = [n for n in z.namelist() if n.lower().endswith(".kml")]
                if not kmls:
                    raise RuntimeError(f"No .kml found in KMZ: {filepath}")
                for name in kmls:
                    with z.open(name) as kml:
                        with tempfile.NamedTemporaryFile(
                            suffix=".kml", delete=False
                        ) as tmp:
                            tmp.write(kml.read())
                            tmp.flush()
                            gdfs.append(gpd.read_file(tmp.name, driver="KML"))
            return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
        else:
            return gpd.read_file(filepath)

    def load_and_reproject(self) -> None:
        """Read all files and reproject to target CRS."""
        files = self.collect_files()
        if not files:
            raise RuntimeError(f"No supported vector files found in {self.input_dir}")
        self.logger.info("Loading vector files: %s", files)

        gdfs = []
        for fp in files:
            try:
                gdf = self._read_file(fp)
                if gdf.crs is None:
                    self.logger.warning(
                        "No CRS on %s, assuming %s", fp, self.target_crs
                    )
                    gdf = gdf.set_crs(self.target_crs)
                gdf = gdf.to_crs(self.target_crs)
                gdfs.append(gdf)
            # pylint: disable=broad-exception-caught
            except Exception as e:
                self.logger.warning("Skipping file %s: %s", fp, e)

        if not gdfs:
            raise RuntimeError("All vector files failed to load or no valid geometries")
        self.gdf = gpd.GeoDataFrame(
            pd.concat(gdfs, ignore_index=True), crs=self.target_crs
        )

    def repair_geometries(self) -> None:
        """Repair invalid geometries and explode multipart features."""
        if self.gdf is None:
            raise RuntimeError(
                "No GeoDataFrame to repair; run load_and_reproject first"
            )
        # Repair invalid
        self.gdf["geometry"] = self.gdf.geometry.buffer(0)
        # Explode
        self.gdf = self.gdf.explode(ignore_index=True)
        # Drop invalid/null
        self.gdf = self.gdf[self.gdf.geometry.notnull() & self.gdf.geometry.is_valid]

    def ensure_id(self) -> None:
        """Ensure a sequential ID column exists."""
        if self.gdf is None:
            return
        self.gdf.reset_index(drop=True, inplace=True)
        self.gdf[self.id_col] = self.gdf.index.astype(int) + 1

    @staticmethod
    def compute_area(gdf: gpd.GeoDataFrame, area_crs: int = 8857) -> None:
        """Add an ``area_m2`` column to ``gdf`` using ``area_crs``.

        Parameters
        ----------
        gdf:
            GeoDataFrame whose area should be computed.
        area_crs:
            Projected CRS (defaults to EPSG:8857) used to calculate area in
            square metres.
        """
        area_gdf = gdf.to_crs(epsg=area_crs)
        gdf["area_m2"] = area_gdf.geometry.area

    def calculate_area(self) -> None:
        """Calculate area in m2 using the area CRS."""
        if self.gdf is None:
            return
        self.compute_area(self.gdf, self.area_crs)

    def add_username(self) -> None:
        """Add a 'username' column based on the input directory name."""
        if self.gdf is None:
            return
        username = os.path.basename(os.path.normpath(self.input_dir))
        self.gdf["username"] = username

    def drop_z(self) -> None:
        """Drop the Z dimension from geometries."""
        if self.gdf is None:
            return
        self.gdf["geometry"] = self.gdf["geometry"].apply(
            lambda geom: wkb.loads(wkb.dumps(geom, output_dimension=2))
        )

    def run(self) -> gpd.GeoDataFrame:
        """Execute the full preprocessing pipeline and return a GeoDataFrame."""
        self.load_and_reproject()
        self.repair_geometries()
        self.ensure_id()
        self.calculate_area()
        self.add_username()
        self.drop_z()
        return self.gdf
