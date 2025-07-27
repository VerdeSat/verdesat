import numpy as np
from verdesat.biodiv.metrics import MetricEngine, LandcoverResult


def test_calc_intactness():
    arr = np.array([[1, 2], [3, 4]])
    res = LandcoverResult(arr)
    eng = MetricEngine()
    assert eng.calc_intactness(res) == 0.5


def test_calc_shannon():
    arr = np.array([[1, 1, 2, 2], [3, 3, 3, 3]])
    res = LandcoverResult(arr)
    eng = MetricEngine()
    h = eng.calc_shannon(res)
    expected = -(0.25 * np.log(0.25) + 0.25 * np.log(0.25) + 0.5 * np.log(0.5))
    assert abs(h - expected) < 1e-6


def test_calc_fragmentation():
    arr = np.array([[1, 1], [2, 2]])
    res = LandcoverResult(arr)
    eng = MetricEngine()
    stats = eng.calc_fragmentation(res, biome_id=1)
    assert stats.edge_density == 0.5
    assert stats.normalised_density == 0.5
