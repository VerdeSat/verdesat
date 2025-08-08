from __future__ import annotations

import types

import pytest

from verdesat.webapp.services import r2
from verdesat.core.config import ConfigValidationError


def test_client_missing_config_raises(monkeypatch):
    monkeypatch.setattr(r2, "_R2_CFG", {})
    r2._client.cache_clear()
    with pytest.raises(ConfigValidationError):
        r2._client()


def test_signed_url_uses_client(monkeypatch):
    cfg = {"endpoint": "e", "key": "k", "secret": "s", "bucket": "b"}
    monkeypatch.setattr(r2, "_R2_CFG", cfg)

    class FakeClient:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):  # noqa: N803
            assert Params == {"Bucket": "b", "Key": "path"}
            assert ExpiresIn == 123
            return "http://signed"

    fake_client = FakeClient()
    monkeypatch.setattr(
        r2, "boto3", types.SimpleNamespace(client=lambda *a, **k: fake_client)
    )
    r2._client.cache_clear()
    url = r2.signed_url("path", expires=123)
    assert url == "http://signed"


def test_upload_bytes_calls_put_object(monkeypatch):
    cfg = {"endpoint": "e", "key": "k", "secret": "s", "bucket": "b"}
    monkeypatch.setattr(r2, "_R2_CFG", cfg)

    class FakeClient:
        def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
            self.called_with = (Bucket, Key, Body, ContentType)

    fake_client = FakeClient()
    monkeypatch.setattr(
        r2, "boto3", types.SimpleNamespace(client=lambda *a, **k: fake_client)
    )
    r2._client.cache_clear()
    r2.upload_bytes("key.txt", b"data", content_type="text/plain")
    assert fake_client.called_with == ("b", "key.txt", b"data", "text/plain")
