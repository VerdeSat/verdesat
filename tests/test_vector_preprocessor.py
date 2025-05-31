# pylint: disable=redefined-outer-name
"""
Tests for the VectorPreprocessor: ensure shapefile, KML, KMZ handling and CLI 'prepare' command.
"""

import shutil
import zipfile

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from click.testing import CliRunner

from verdesat.ingestion.vector_preprocessor import VectorPreprocessor
from verdesat.core.cli import cli


@pytest.fixture
def shapefile_dir(tmp_path):
    """
    Create a temporary directory with a simple shapefile containing one polygon.
    Returns the directory path.
    """
    dir_path = tmp_path / "shp_dir"
    dir_path.mkdir()
    # Create a single-polygon GeoDataFrame
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = gpd.GeoDataFrame({"name": ["poly1"], "geometry": [poly]}, crs="EPSG:4326")
    # Write shapefile (produces .shp, .shx, .dbf, .prj)
    gdf.to_file(dir_path / "layer.shp")
    return dir_path


@pytest.fixture
def kml_dir(tmp_path):
    """
    Create a temporary directory with a simple KML file containing one polygon.
    Returns the directory path.
    """
    dir_path = tmp_path / "kml_dir"
    dir_path.mkdir()
    poly = Polygon([(2, 2), (2, 3), (3, 3), (3, 2)])
    gdf = gpd.GeoDataFrame({"name": ["poly2"], "geometry": [poly]}, crs="EPSG:4326")
    # Write KML
    gdf.to_file(dir_path / "layer.kml", driver="KML")
    return dir_path


@pytest.fixture
def kmz_dir(tmp_path):
    """
    Create a temporary directory with a simple KMZ (zipped KML) containing one polygon.
    Returns the directory path.
    """
    dir_path = tmp_path / "kmz_dir"
    dir_path.mkdir()
    poly = Polygon([(4, 4), (4, 5), (5, 5), (5, 4)])
    gdf = gpd.GeoDataFrame({"name": ["poly3"], "geometry": [poly]}, crs="EPSG:4326")
    kml_path = dir_path / "layer.kml"
    gdf.to_file(kml_path, driver="KML")
    kmz_path = dir_path / "layer.kmz"
    # Zip the KML into KMZ
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(kml_path, arcname="layer.kml")
    # Remove the original KML
    kml_path.unlink()
    return dir_path


@pytest.fixture
def invalid_geojson_file(tmp_path):
    """
    Create a temporary directory with an invalid GeoJSON file.
    Returns the directory path.
    """
    dir_path = tmp_path / "invalid_dir"
    dir_path.mkdir()
    invalid_path = dir_path / "bad.geojson"
    # Write invalid JSON content
    invalid_path.write_text("{not: valid json}", encoding="utf-8")
    return dir_path


def test_only_shapefile(shapefile_dir):
    """
    If a lone shapefile lives in the dir, VectorPreprocessor returns a GeoDataFrame
    with one polygon and writes the processed GeoJSON.
    """
    # Run the processor
    vp = VectorPreprocessor(str(shapefile_dir))
    result_gdf = vp.run()
    # Check GeoDataFrame returned has one feature
    assert len(result_gdf) == 1
    assert "area_m2" in result_gdf.columns
    assert "username" in result_gdf.columns
    # Also test CLI 'prepare' writes file
    runner = CliRunner()
    result = runner.invoke(cli, ["prepare", str(shapefile_dir)])
    assert result.exit_code == 0
    output_file = shapefile_dir / f"{shapefile_dir.name}_processed.geojson"
    assert output_file.exists()
    # Read back the GeoJSON to confirm one feature
    gdf2 = gpd.read_file(str(output_file))
    assert len(gdf2) == 1


def test_multiple_formats(tmp_path, shapefile_dir, kml_dir, kmz_dir):
    """
    When shapefile, KML, and KMZ coexist in the same directory, all features are ingested.
    """
    # Combine all sample dirs into one parent
    parent_dir = tmp_path / "combined"
    parent_dir.mkdir()
    # Copy shapefile, KML, KMZ contents into parent_dir
    for src in (shapefile_dir, kml_dir, kmz_dir):
        for item in src.iterdir():
            shutil.copy(item, parent_dir / item.name)
    # Run processor on combined directory
    vp = VectorPreprocessor(str(parent_dir))
    result_gdf = vp.run()
    # Expect 3 features (one per source)
    assert len(result_gdf) == 3


def test_skip_invalid_geojson(shapefile_dir, invalid_geojson_file):
    """
    If both valid and invalid files exist, invalid ones are skipped, valid ones processed.
    """
    # Copy shapefile into invalid_dir to simulate mixing
    invalid_dir_path = invalid_geojson_file
    for item in shapefile_dir.iterdir():
        shutil.copy(item, invalid_dir_path / item.name)
    # Run on invalid_geojson_file directory (which now also has shapefile)
    vp = VectorPreprocessor(str(invalid_geojson_file))
    result_gdf = vp.run()
    # Only the one valid polygon should be present
    assert len(result_gdf) == 1


def test_no_supported_files(tmp_path):
    """
    If no supported vector files exist, VectorPreprocessor.run() raises RuntimeError.
    """
    # Create a directory with a non-vector file
    dir_path = tmp_path / "empty_dir"
    dir_path.mkdir()
    (dir_path / "readme.txt").write_text("no vectors here", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        VectorPreprocessor(str(dir_path)).run()
    assert "No supported vector files" in str(exc.value)
