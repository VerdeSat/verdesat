import json
import pytest
import pandas as pd


@pytest.fixture
def sample_geojson(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
                },
            }
        ],
    }
    path = tmp_path / "sample.geojson"
    path.write_text(json.dumps(geojson))
    return path


@pytest.fixture
def sample_timeseries_csv(tmp_path):
    data = pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-02-01"],
            "id": [1, 1],
            "mean_ndvi": [0.5, 0.6],
        }
    )
    path = tmp_path / "timeseries.csv"
    data.to_csv(path, index=False)
    return path


@pytest.fixture
def sample_decomp_dir(tmp_path):
    d = tmp_path / "decomp"
    d.mkdir()
    # create a dummy decomposition PNG
    (d / "1_decomposition.png").write_bytes(b"")
    return d


@pytest.fixture
def sample_chips_dir(tmp_path):
    d = tmp_path / "chips"
    d.mkdir()
    # create a dummy chip PNG matching gallery pattern
    (d / "1_2020-01-01.png").write_bytes(b"")
    return d
