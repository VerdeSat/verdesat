"""Lightweight service-layer helpers used by the CLI and tests."""

from importlib import import_module

__all__ = [
    "download_timeseries",
    "build_report",
    "LandcoverService",
    "compute_bscores",
    "compute_msa_means",
]


def __getattr__(name):
    if name == "download_timeseries":
        return import_module(".timeseries", __name__).download_timeseries
    if name == "build_report":
        return import_module(".report", __name__).build_report
    if name == "LandcoverService":
        return import_module(".landcover", __name__).LandcoverService
    if name == "compute_bscores":
        return import_module(".bscore", __name__).compute_bscores
    if name == "compute_msa_means":
        return import_module(".msa", __name__).compute_msa_means
    raise AttributeError(name)
