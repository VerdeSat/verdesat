from __future__ import annotations

import pandas as pd

from verdesat.ingestion.downloader import BaseDownloader, EarthEngineDownloader


class DummyDownloader(BaseDownloader):
    """Downloader that records attempts and can fail once per chunk."""

    def __init__(self) -> None:
        super().__init__(max_retries=2)
        self.attempts: dict[tuple[str, str], int] = {}

    def download_chunk(self, start: str, end: str, *args, **kwargs):
        key = (start, end)
        self.attempts[key] = self.attempts.get(key, 0) + 1
        if key == ("2020-01-02", "2020-01-03") and self.attempts[key] == 1:
            raise ValueError("temporary failure")
        return pd.DataFrame({"id": [1], "date": [start], "value": [1.0]})


def test_build_chunks_generates_expected_ranges():
    chunks = BaseDownloader.build_chunks("2020-01-01", "2020-01-04", "2D")
    assert chunks == [
        ("2020-01-01", "2020-01-01"),
        ("2020-01-02", "2020-01-03"),
        ("2020-01-04", "2020-01-04"),
    ]


def test_download_with_chunks_retries_and_combines(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    dler = DummyDownloader()
    df = dler.download_with_chunks("2020-01-01", "2020-01-04", "2D")
    # ensure retry happened
    assert dler.attempts[("2020-01-02", "2020-01-03")] == 2
    # three chunks concatenated
    assert len(df) == 3


def test_earth_engine_downloader_builds_dataframe(monkeypatch, dummy_aoi):
    class FakeCollection:
        def map(self, func):  # pragma: no cover - behaviour is trivial
            return self

        def flatten(self):  # pragma: no cover - behaviour is trivial
            return self

        def getInfo(self):
            return {
                "features": [
                    {"properties": {"id": 1, "date": "2020-01-01", "mean": 0.5}}
                ]
            }

    class FakeEE:
        def initialize(self):  # pragma: no cover - trivial
            return None

        def get_image_collection(self, *args, **kwargs):  # pragma: no cover
            return FakeCollection()

    # mask_collection should act as identity for this test
    monkeypatch.setattr(
        "verdesat.ingestion.downloader.mask_collection", lambda coll, sensor: coll
    )
    monkeypatch.setattr("ee.Geometry", lambda geojson: geojson)  # type: ignore[attr-defined]
    monkeypatch.setattr("ee.Feature", lambda geom, props: {"geometry": geom, **props})  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "ee.FeatureCollection", lambda features: features
    )  # type: ignore[attr-defined]

    class DummySensor:
        collection_id = "dummy"

    dler = EarthEngineDownloader(DummySensor(), ee_manager=FakeEE())
    df = dler.download_chunk(
        "2020-01-01", "2020-01-02", dummy_aoi, scale=10, index="ndvi", value_col=None
    )
    assert list(df.columns) == ["id", "date", "mean_ndvi"]
    assert df.iloc[0]["mean_ndvi"] == 0.5
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
