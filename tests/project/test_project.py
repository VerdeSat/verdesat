from __future__ import annotations

import pytest

from verdesat.core.config import ConfigManager
from verdesat.project.project import Project


def _geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {"id": 2},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[1.0, 1.0], [1.0, 2.0], [2.0, 2.0], [2.0, 1.0], [1.0, 1.0]]
                    ],
                },
            },
        ],
    }


def test_from_geojson_builds_aois() -> None:
    config = ConfigManager()
    project = Project.from_geojson(_geojson(), config, name="Demo", customer="Client")
    assert project.name == "Demo"
    assert project.customer == "Client"
    assert len(project.aois) == 2
    assert project.rasters == {}
    assert project.metrics == {}


def test_attach_rasters() -> None:
    config = ConfigManager()
    project = Project.from_geojson(_geojson(), config, name="Demo", customer="Client")
    project.attach_rasters(
        {"1": "a_ndvi.tif"}, {"1": "a_msavi.tif", "2": "b_msavi.tif"}
    )
    assert project.rasters["1"]["ndvi"] == "a_ndvi.tif"
    assert project.rasters["1"]["msavi"] == "a_msavi.tif"
    assert project.rasters["2"]["msavi"] == "b_msavi.tif"
    assert "ndvi" not in project.rasters["2"]


def test_attach_metrics() -> None:
    config = ConfigManager()
    project = Project.from_geojson(_geojson(), config, name="Demo", customer="Client")
    project.attach_metrics({"biodiv": 0.5, "vi": 0.7})
    assert project.metrics["biodiv"] == 0.5
    assert project.metrics["vi"] == 0.7


def test_from_geojson_reads_metadata_and_area() -> None:
    config = ConfigManager()
    gj = {
        "type": "FeatureCollection",
        "metadata": {"name": "MetaProj", "customer": "MetaCust"},
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]
                    ],
                },
            }
        ],
    }
    project = Project.from_geojson(gj, config)
    assert project.name == "MetaProj"
    assert project.customer == "MetaCust"
    assert "area_m2" in project.aois[0].static_props
    assert project.aois[0].static_props["area_m2"] > 0


def test_from_geojson_sanitizes_metadata() -> None:
    config = ConfigManager()
    gj = _geojson()
    gj["metadata"] = {"name": "../bad*proj", "customer": "Cust<>\n"}
    project = Project.from_geojson(gj, config)
    assert project.name == "badproj"
    assert project.customer == "Cust"


def test_from_geojson_validates_input() -> None:
    config = ConfigManager()
    with pytest.raises(ValueError):
        Project.from_geojson({"type": "Feature"}, config)
    with pytest.raises(ValueError):
        Project.from_geojson({"type": "FeatureCollection"}, config)
