import os
from types import SimpleNamespace
import geopandas as gpd
from shapely.geometry import Polygon
from shapely import wkt
from verdesat.geo.aoi import AOI

import pytest

from verdesat.biodiv.gbif_validator import OccurrenceService, plot_score_vs_density


def dummy_geojson():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
                },
                "properties": {},
            }
        ],
    }


def _fake_records(n, lat=0.5, lon=0.5):
    return [{"decimalLatitude": lat, "decimalLongitude": lon} for _ in range(n)]


def test_fetch_occurrences_gbif_only(monkeypatch):
    calls = {"ebird": 0, "inat": 0}

    def fake_gbif(**_k):
        return {"results": _fake_records(300)}

    def fail_ebird(*_a, **_k):
        calls["ebird"] += 1
        return []

    def fail_inat(*_a, **_k):
        calls["inat"] += 1
        return {"results": []}

    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.gbif_occ",
        SimpleNamespace(search=fake_gbif),
    )
    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.get_nearby_observations", fail_ebird
    )
    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.inat_get_observations", fail_inat
    )

    svc = OccurrenceService()
    gdf = svc.fetch_occurrences(dummy_geojson())
    assert len(gdf) == 300
    assert gdf["source"].unique().tolist() == ["gbif"]
    # Fallbacks shouldn't run when GBIF returns ample records
    assert calls == {"ebird": 0, "inat": 0}


def test_fetch_occurrences_with_fallbacks(monkeypatch):
    def fake_gbif(**_k):
        return {"results": _fake_records(10)}

    def fake_ebird(token, lat, lon, **_k):
        return _fake_records(5, lat, lon)

    def fake_inat(**_k):
        return {"results": _fake_records(3)}

    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.gbif_occ",
        SimpleNamespace(search=fake_gbif),
    )
    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.get_nearby_observations", fake_ebird
    )
    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.inat_get_observations", fake_inat
    )
    os.environ["EBIRD_TOKEN"] = "x"

    svc = OccurrenceService()
    gdf = svc.fetch_occurrences(dummy_geojson())
    assert len(gdf) == 18
    assert set(gdf["source"]) == {"gbif", "ebird", "inat"}


def test_fetch_occurrences_crs_conversion(monkeypatch):
    captured = {}

    def fake_gbif(geometry, **_k):
        captured["geom"] = geometry
        return {"results": _fake_records(1)}

    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.gbif_occ",
        SimpleNamespace(search=fake_gbif),
    )

    svc = OccurrenceService()
    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0, 0), (0, 1000), (1000, 1000), (1000, 0)])]},
        crs="EPSG:3857",
    )
    svc.fetch_occurrences(gdf)
    poly = wkt.loads(captured["geom"])
    assert poly.bounds[2] <= 180 and poly.bounds[3] <= 90


def test_occurrence_density():
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = gpd.GeoDataFrame({"geometry": [poly, poly]}, crs="EPSG:4326")
    svc = OccurrenceService()
    dens = svc.occurrence_density_km2(gdf, 1.0)
    assert dens == 2.0


def test_fetch_occurrences_with_shapely(monkeypatch):
    def fake_gbif(**_k):
        return {"results": _fake_records(2)}

    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.gbif_occ",
        SimpleNamespace(search=fake_gbif),
    )

    svc = OccurrenceService()
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = svc.fetch_occurrences(poly)
    assert len(gdf) == 2


def test_fetch_occurrences_with_aoi(monkeypatch):
    def fake_gbif(**_k):
        return {"results": _fake_records(1)}

    monkeypatch.setattr(
        "verdesat.biodiv.gbif_validator.gbif_occ",
        SimpleNamespace(search=fake_gbif),
    )

    aoi = AOI(Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]), static_props={"id": 1})
    svc = OccurrenceService()
    gdf = svc.fetch_occurrences(aoi)
    assert len(gdf) == 1


def test_plot_score_vs_density(tmp_path):
    out = tmp_path / "plot.png"
    plot_score_vs_density([0.1, 0.2], [1, 2], str(out))
    assert out.exists() and out.stat().st_size > 0
