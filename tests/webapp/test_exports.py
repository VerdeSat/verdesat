import pandas as pd

from verdesat.core.config import ConfigManager
from verdesat.project.project import Project
from verdesat.webapp.services import exports


def test_export_project_pdf(monkeypatch):
    metrics = pd.DataFrame({"id": [1], "bscore": [0.5]})
    project = Project("Demo", "VerdeSat", [], ConfigManager())

    uploaded: dict[str, tuple[str, bytes, str]] = {}

    def fake_upload(key: str, data: bytes, *, content_type: str = "") -> None:
        uploaded["args"] = (key, data, content_type)

    def fake_signed_url(key: str) -> str:
        return f"https://example.com/{key}"

    monkeypatch.setattr(exports, "upload_bytes", fake_upload)
    monkeypatch.setattr(exports, "signed_url", fake_signed_url)

    url = exports.export_project_pdf(metrics, project)

    assert url == f"https://example.com/{uploaded['args'][0]}"
    assert uploaded["args"][2] == "application/pdf"
    assert uploaded["args"][1].startswith(b"%PDF")
