"""
Module `ingestion.indices` provides generic spectral index computation
by loading formulas from `resources/index_formulas.json`.
"""

import json
from pathlib import Path
from ee import Image

# Load index formulas from resources
_FORMULA_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "index_formulas.json"
)
with open(_FORMULA_PATH, "r", encoding="utf-8") as _f:
    INDEX_REGISTRY = json.load(_f)


def compute_index(img: Image, index: str) -> Image:
    """
    Compute a named spectral index on the given EE Image using the JSON formula.

    Args:
        img: ee.Image with bands already renamed to standard aliases (lowercase).
        index: one of the keys in INDEX_REGISTRY (case-insensitive).

    Returns:
        ee.Image of the computed index band, named by the lowercase index key.
    """
    key = index.lower()
    if key not in INDEX_REGISTRY:
        raise ValueError(
            f"Index '{index}' not supported. Choose from: {list(INDEX_REGISTRY)}"
        )
    formula = INDEX_REGISTRY[key]
    expr = formula["expr"]
    bands = formula["bands"]
    params = formula.get("params", {})
    # Build the parameter map: alias tokens (uppercase) to ee.Image or numeric value
    token_map = {}
    for alias in bands:
        # Map alias uppercased in formula to the corresponding band in img
        token_map[alias.upper()] = img.select(alias)
    # Add numeric parameters
    for param_key, param_val in params.items():
        token_map[param_key.upper()] = param_val
    # Evaluate the expression and rename output to the index name
    result = img.expression(expr, token_map).rename(key)
    return result
