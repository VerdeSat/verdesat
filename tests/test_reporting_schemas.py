from dataclasses import is_dataclass

from verdesat.schemas.reporting import (
    LABELS,
    AoiContext,
    MetricsRow,
    ProjectContext,
)


def test_project_context_defaults():
    ctx = ProjectContext(project_id="p1", project_name="Demo")
    assert ctx.owner is None
    assert ctx.countries_iso3 is None
    assert is_dataclass(ctx)


def test_aoi_context_required_and_defaults():
    aoi = AoiContext(aoi_id="a1")
    assert aoi.aoi_name is None
    assert aoi.tags is None
    assert is_dataclass(aoi)


def test_metrics_row_defaults_and_labels():
    row = MetricsRow()
    assert row.ndvi_mean is None
    assert LABELS["ndvi_mean"] == "NDVI μ"
    assert "bscore" in LABELS
