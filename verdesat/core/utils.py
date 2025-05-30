import logging  # type: ignore
import os
import geopandas as gpd  # type: ignore


def setup_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def read_geojson(path: str):
    """Load GeoJSON into a GeoDataFrame."""
    if not os.path.exists(path):
        logging.error("File not found: %s", path)
        raise FileNotFoundError(path)
    return gpd.read_file(path)
