import math
import pytest
from verdesat.ingestion.chips import compute_buffer


def test_compute_buffer_multipolygon():
    poly = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
            [[[4, 0], [4, 1], [5, 1], [5, 0], [4, 0]]],
        ],
    }
    result = compute_buffer([{"geometry": poly}], 0, 10)
    mean_lat = 0.5
    width_m = 5 * 111320.0 * math.cos(math.radians(mean_lat))
    height_m = 1 * 111320.0
    extent_max = max(abs(width_m), abs(height_m))
    expected = extent_max * 0.1
    assert result == pytest.approx(expected)
