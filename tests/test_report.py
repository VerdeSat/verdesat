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
            "var": ["ndvi", "ndvi"],
            "stat": ["raw", "raw"],
            "value": [0.5, 0.6],
            "aoi_id": [1, 1],
            "freq": ["monthly", "monthly"],
            "source": ["S2", "S2"],
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


def test_build_report_custom_index(sample_geojson, tmp_path):
    ts_csv = tmp_path / "ts.csv"
    pd.DataFrame(
        {
            "date": ["2020-01-01"],
            "var": ["evi"],
            "stat": ["raw"],
            "value": [0.4],
            "aoi_id": [1],
            "freq": ["monthly"],
            "source": ["S2"],
        }
    ).to_csv(ts_csv, index=False)
    chips_dir = tmp_path / "chips"
    chips_dir.mkdir()
    (chips_dir / "EVI_1_2020-01-01.png").write_bytes(b"")
    from verdesat.visualization.report import build_report

    out_html = tmp_path / "report.html"
    build_report(
        geojson_path=sample_geojson,
        timeseries_csv=str(ts_csv),
        chips_dir=str(chips_dir),
        output_path=str(out_html),
        index_name="evi",
    )
    html = out_html.read_text()
    assert "EVI_1_2020-01-01.png" in html
