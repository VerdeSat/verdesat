import os, glob, logging, zipfile, tempfile
from shapely import wkb
import geopandas as gpd
import pandas as pd
from verdesat.core.config import SUPPORTED_INPUT_FORMATS


# Configure logging
logger = logging.getLogger(__name__)


class ShapefilePreprocessor:
    """
    Processes vector files in a directory:
    - Loads & reprojects to EPSG:4326
    - Fixes invalid geometries & explodes multipolygons
    - Calculates area in square meters using Equal Earth projection (EPSG:8857)
    - Adds a username field based on the directory name
    - Writes a combined GeoJSON to the input directory
    """

    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        # Whitelist of supported file extensions
        self.exts = [e.lower() for e in SUPPORTED_INPUT_FORMATS]
        self.gdf = gpd.GeoDataFrame()

    def _collect_files(self) -> list[str]:
        """Gather all supported vector files in the input directory (recursive)."""
        matches = []
        for root, _, files in os.walk(self.input_dir):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in self.exts:
                    matches.append(os.path.join(root, fname))
        return matches

    def _read_kmz(self, filepath: str):
        """
        Extracts all KMLs from a KMZ archive to a temp file and reads it.
        """
        with zipfile.ZipFile(filepath, "r") as z:
            kmls = [n for n in z.namelist() if n.lower().endswith(".kml")]
            if not kmls:
                raise RuntimeError("No .kml in KMZ")
            gdfs = []
            for name in kmls:
                with z.open(name) as kml:
                    with tempfile.NamedTemporaryFile(
                        suffix=".kml", delete=False
                    ) as tmp:
                        tmp.write(kml.read())
                        tmp.flush()
                        gdfs.append(gpd.read_file(tmp.name, driver="KML"))
            return pd.concat(gdfs, ignore_index=True)

    def load_and_reproject(self):
        gdfs = []
        paths = self._collect_files()
        if not paths:
            raise RuntimeError(f"No supported vector files found in {self.input_dir}")
        # Log and print the list of files to be processed
        logger.info(f"Processing input files: {paths}")
        for filepath in paths:
            try:
                if filepath.lower().endswith(".kmz"):
                    gdf = self._read_kmz(filepath)
                else:
                    gdf = gpd.read_file(filepath)
                if gdf.crs is None:
                    logger.warning(f"No CRS on {filepath}, assuming EPSG:4326")
                    gdf = gdf.set_crs(epsg=4326)
                gdf = gdf.to_crs(epsg=4326)
                gdfs.append(gdf)
            except Exception as e:
                logger.warning(f"Skipping file {filepath}: {e}")
        if not gdfs:
            raise RuntimeError(f"No valid geospatial files found in {self.input_dir}")
        self.gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")

    def fix_and_explode(self):
        # Repair invalid geometries
        self.gdf["geometry"] = self.gdf.geometry.buffer(0)
        # Explode multi-part geometries
        self.gdf = self.gdf.explode(index_parts=False)
        # Remove empty or invalid
        self.gdf = self.gdf[self.gdf.geometry.notnull() & self.gdf.geometry.is_valid]

    def calculate_area(self, area_crs: int = 8857):
        # Project for area calc
        area_gdf = self.gdf.to_crs(epsg=area_crs)
        self.gdf["area_m2"] = area_gdf.geometry.area

    def add_username(self):
        username = os.path.basename(os.path.normpath(self.input_dir))
        self.gdf["username"] = username

    def ensure_id(self):
        # Always overwrite any existing 'id' field
        self.gdf.reset_index(drop=True, inplace=True)
        self.gdf["id"] = self.gdf.index.astype(int) + 1
        logger.info("Overwritten 'id' column with sequential identifiers")

    def drop_z(self):
        """
        Drop Z dimension from all geometries by dumping to 2D WKB and reloading.
        """
        self.gdf["geometry"] = self.gdf["geometry"].apply(
            lambda geom: wkb.loads(wkb.dumps(geom, output_dimension=2))
        )
        logger.info("Dropped Z dimension from geometries")

    def save(self):
        username = os.path.basename(os.path.normpath(self.input_dir))
        output_path = os.path.join(self.input_dir, f"{username}_processed.geojson")
        self.gdf.to_file(output_path, driver="GeoJSON")
        logger.info(f"Saved processed GeoJSON to {output_path}")

    def run(self):
        self.load_and_reproject()
        self.fix_and_explode()
        self.ensure_id()
        self.calculate_area()
        self.add_username()
        self.drop_z()
        self.save()
