"""Lightweight service-layer helpers used by the CLI and tests."""

from importlib import import_module

__all__ = ["download_timeseries", "build_report", "LandcoverService"]


def __getattr__(name):
    if name == "download_timeseries":
        return import_module(".timeseries", __name__).download_timeseries
    if name == "build_report":
        return import_module(".report", __name__).build_report
    if name == "LandcoverService":
        return import_module(".landcover", __name__).LandcoverService
    raise AttributeError(name)
