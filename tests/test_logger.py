# pylint: disable=unused-import, protected-access, missing-module-docstring
"""
Tests for the logging formatter and Logger class.
"""

import os
import json
import logging
import pytest

from verdesat.core.logger import Logger


@pytest.fixture(autouse=True)
def reset_logger(monkeypatch):
    """
    Reset Logger configuration and environment variables before each test.
    """
    Logger._configured = False
    # Clear env vars
    monkeypatch.delenv("VERDESAT_LOG_FMT", raising=False)
    monkeypatch.delenv("VERDESAT_LOG_LEVEL", raising=False)
    # Remove all handlers
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    yield
    # Clean up after
    for h in list(root.handlers):
        root.removeHandler(h)


def test_text_logging_default(capsys):
    """
    By default, logs should be in text format on stderr.
    """
    Logger.setup()
    logger = Logger.get_logger("test")
    logger.info("hello world")
    captured = capsys.readouterr()
    assert "INFO" in captured.err
    assert "test" in captured.err
    assert "hello world" in captured.err


def test_json_logging_env(capsys):
    """
    When VERDESAT_LOG_FMT=json and VERDESAT_LOG_LEVEL=DEBUG, output must be JSON.
    """
    os.environ["VERDESAT_LOG_FMT"] = "json"
    os.environ["VERDESAT_LOG_LEVEL"] = "DEBUG"
    # Reset state
    Logger._configured = False
    logging.getLogger().handlers.clear()

    Logger.setup()
    logger = Logger.get_logger("testjson")
    logger.debug("debug message")
    captured = capsys.readouterr()
    record = json.loads(captured.err.strip())
    assert record["level"] == "DEBUG"
    assert record["name"] == "testjson"
    assert record["message"] == "debug message"
    assert "timestamp" in record


def test_no_duplicate_handlers():
    """
    Calling setup() twice should not add duplicate handlers.
    """
    # Reset state
    Logger._configured = False
    logging.getLogger().handlers.clear()

    Logger.setup()
    Logger.setup()
    handlers = [
        h for h in logging.getLogger().handlers if isinstance(h, logging.StreamHandler)
    ]
    assert len(handlers) == 1
