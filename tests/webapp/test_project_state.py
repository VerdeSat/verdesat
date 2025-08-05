from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Polygon

from verdesat.geo.aoi import AOI
from verdesat.project.project import VerdeSatProject
from verdesat.core.config import ConfigManager
from verdesat.core.storage import LocalFS
from verdesat.webapp.services.project_state import persist_project


class TempStorage(LocalFS):
    def __init__(self, base: str) -> None:  # pragma: no cover - simple
        self.base = base

    def join(self, *parts: str) -> str:  # pragma: no cover - simple
        return str(Path(self.base, *parts))


def test_persist_project(tmp_path):
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    project = VerdeSatProject("TestProj", "Cust", [aoi], ConfigManager())
    storage = TempStorage(str(tmp_path))
    uri = persist_project(project, storage)
    saved = json.loads(Path(uri).read_text())
    assert saved["metadata"]["name"] == "TestProj"
    assert len(saved["features"]) == 1
