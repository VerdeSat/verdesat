from verdesat.visualization.report import build_report


def test_build_report(
    tmp_path, sample_geojson, sample_timeseries_csv, sample_decomp_dir, sample_chips_dir
):
    out = tmp_path / "report.html"
    build_report(
        str(sample_geojson),
        str(sample_timeseries_csv),
        str(sample_decomp_dir),
        str(sample_chips_dir),
        str(out),
        title="Test",
    )
    assert out.exists()
    content = out.read_text()
    assert "<html" in content and "Test" in content
