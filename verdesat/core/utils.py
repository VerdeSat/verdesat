"""Utility helpers for core modules."""

from __future__ import annotations

import os
import re


def sanitize_identifier(identifier: str) -> str:
    """Return a filesystem-safe version of ``identifier``.

    The input string is reduced to its basename and any character outside the
    ``[A-Za-z0-9_]`` set is replaced with an underscore.  If the sanitized value
    would be empty, ``"unknown"`` is returned.
    """
    base = os.path.basename(identifier)
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", base)
    return sanitized or "unknown"
