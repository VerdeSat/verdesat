import os
import pytest
import geopandas as gpd
from click.testing import CliRunner
from verdesat.ingestion.shapefile_preprocessor import ShapefilePreprocessor
from verdesat.core.cli import cli


def test_only_shapefile(tmp_path, sample_shapefile):
    """If a lone shapefile lives in the dir, we get exactly its one feature back."""
    processor = ShapefilePreprocessor(str(sample_shapefile))
    processor.run()
    out = sample_shapefile / f"{sample_shapefile.name}_processed.geojson"
    gdf = gpd.read_file(out)
    assert len(gdf) == 1
    assert "area_m2" in gdf.columns


def test_multiple_formats(tmp_path, sample_shapefile, sample_kml, sample_kmz):
    """When shapefile, KML and KMZ coexist, they all get ingested (3 total)."""
    # Place KML and KMZ into the same directory
    # sample_kml and sample_kmz fixtures already write to tmp_path
    processor = ShapefilePreprocessor(str(tmp_path))
    processor.run()
    out = tmp_path / f"{tmp_path.name}_processed.geojson"
    gdf = gpd.read_file(out)
    assert len(gdf) == 3


def test_skip_invalid_geojson(tmp_path, sample_shapefile, invalid_geojson):
    """Broken GeoJSON should be skipped, not bring the whole run down."""
    processor = ShapefilePreprocessor(str(tmp_path))
    processor.run()
    out = tmp_path / f"{tmp_path.name}_processed.geojson"
    gdf = gpd.read_file(out)
    assert len(gdf) == 1


def test_no_supported_files(tmp_path):
    """If nothing matching our whitelist is here, we raise a RuntimeError."""
    (tmp_path / "readme.txt").write_text("👋")
    with pytest.raises(RuntimeError) as exc:
        ShapefilePreprocessor(str(tmp_path)).run()
    assert "No supported vector files found" in str(exc.value)


def test_cli_prepare(tmp_path, sample_shapefile):
    """CLI 'prepare' command should run and create output file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["prepare", str(sample_shapefile)])
    assert result.exit_code == 0
    assert "GeoJSON written to" in result.output
    out = sample_shapefile / f"{sample_shapefile.name}_processed.geojson"
    assert out.exists()
