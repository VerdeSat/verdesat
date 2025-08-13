from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig
from verdesat.biodiv.metrics import MetricsResult, FragmentStats
from verdesat.services.bscore import compute_bscores


def test_bscore_calculation(tmp_path):
    weights_path = tmp_path / "weights.yaml"
    weights_path.write_text("intactness: 1\nshannon: 1\nfragmentation: 1\nmsa: 1\n")
    weights = WeightsConfig.from_yaml(weights_path)
    calc = BScoreCalculator(weights)
    metrics = MetricsResult(
        intactness_pct=50.0,
        shannon=0.5,
        fragmentation=FragmentStats(edge_density=0.2, frag_norm=0.2),
        msa=0.5,
    )
    score = calc.score(metrics)
    expected = 100 * (0.5 + 0.5 + (1 - 0.2) + 0.5) / 4
    assert score == expected


def test_compute_bscores(monkeypatch, tmp_path):
    def fake_run_all(self, aoi, year, landcover_path=None):
        return MetricsResult(
            intactness_pct=50.0,
            shannon=0.5,
            fragmentation=FragmentStats(edge_density=0.2, frag_norm=0.2),
        )

    monkeypatch.setattr("verdesat.services.bscore.MetricEngine.run_all", fake_run_all)

    monkeypatch.setattr(
        "verdesat.services.bscore.MSAService.mean_msa", lambda self, geom: 0.5
    )

    geojson = tmp_path / "aoi.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[0,0],[0,1],[1,1],[1,0],[0,0]]]},"properties":{"id":1}}]}'
    )
    df = compute_bscores(str(geojson), year=2021, weights=WeightsConfig())

    assert df.loc[0, "aoi_id"] == 1
    assert df.loc[0, "bscore"] > 0
    assert df.loc[0, "intactness_pct"] == 50.0
    assert df.loc[0, "shannon"] == 0.5
    assert df.loc[0, "edge_density"] == 0.2
    assert df.loc[0, "frag_norm"] == 0.2
    assert df.loc[0, "msa"] == 0.5
