"""Helpers for persisting project state.

This module currently provides lightweight hooks for saving a
:class:`~verdesat.project.project.Project` definition using the
existing :class:`~verdesat.core.storage.StorageAdapter`.  In the real
application this would integrate with a database or cloud object store to
persist project state for authenticated users.
"""

from __future__ import annotations

import json
import re
from typing import Any

from shapely.geometry import mapping

from verdesat.project.project import Project
from verdesat.core.storage import StorageAdapter


def persist_project(project: Project, storage: StorageAdapter) -> str:
    """Persist ``project`` definition using ``storage`` and return its URI.

    The project is serialised to GeoJSON where each AOI becomes a feature and
    project-level metadata is stored under the ``metadata`` key.  The returned
    URI can later be used to retrieve the project.  This function serves as a
    placeholder for future database or cloud persistence layers.
    """

    features = [
        {
            "type": "Feature",
            "properties": aoi.static_props,
            "geometry": mapping(aoi.geometry),
        }
        for aoi in project.aois
    ]
    data: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"name": project.name, "customer": project.customer},
    }
    safe_name = re.sub(r"[^A-Za-z0-9_\-]", "", project.name)
    uri = storage.join("projects", f"{safe_name}.geojson")
    storage.write_bytes(uri, json.dumps(data).encode("utf-8"))
    return uri
