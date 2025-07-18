"""Lightweight service-layer helpers used by the CLI and tests."""

from .timeseries import download_timeseries
from .report import build_report

__all__ = ["download_timeseries", "build_report"]
