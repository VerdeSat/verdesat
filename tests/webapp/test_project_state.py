from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Polygon

from verdesat.geo.aoi import AOI
from verdesat.project.project import Project
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
    project = Project("TestProj", "Cust", [aoi], ConfigManager())
    storage = TempStorage(str(tmp_path))
    uri = persist_project(project, storage)
    saved = json.loads(Path(uri).read_text())
    assert saved["metadata"]["name"] == "TestProj"
    assert len(saved["features"]) == 1


def test_persist_project_sanitizes_name(tmp_path):
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    project = Project("../evil", "Cust", [aoi], ConfigManager())
    storage = TempStorage(str(tmp_path))
    uri = persist_project(project, storage)
    saved_path = Path(uri)
    assert saved_path.parent == tmp_path / "projects"
    assert saved_path.name == "evil.geojson"
    saved = json.loads(saved_path.read_text())
    assert saved["metadata"]["name"] == "../evil"


def test_persist_project_handles_special_chars(tmp_path):
    aoi = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": 1})
    project = Project("my!@#../proj", "Cust", [aoi], ConfigManager())
    storage = TempStorage(str(tmp_path))
    uri = persist_project(project, storage)
    saved_path = Path(uri)
    assert saved_path.parent == tmp_path / "projects"
    assert saved_path.name == "myproj.geojson"
    saved = json.loads(saved_path.read_text())
    assert saved["metadata"]["name"] == "my!@#../proj"
