from __future__ import annotations

"""Minimal service base class providing a logger."""

import logging
from verdesat.core.logger import Logger


class BaseService:
    """Base class for service helpers."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or Logger.get_logger(__name__)
