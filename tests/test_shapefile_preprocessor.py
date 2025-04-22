import os
import geopandas as gpd
from verdesat.ingestion.shapefile_preprocessor import ShapefilePreprocessor


def test_processor_creates_output(tmp_path, sample_shapefile):
    # copy or generate a tiny shapefile into tmp_path
    processor = ShapefilePreprocessor(str(tmp_path))
    processor.run()
    out = tmp_path / f"{tmp_path.name}_processed.geojson"
    assert out.exists()
    gdf = gpd.read_file(out)
    assert "id" in gdf.columns
    assert "area_m2" in gdf.columns
