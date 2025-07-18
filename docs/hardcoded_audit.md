# Hardcoded Parameter Audit (2025-07)

The major constants previously scattered across the codebase are now configurable.
`ConfigManager` exposes defaults like `DEFAULT_INDEX`, `VALUE_COL_TEMPLATE` and
`DEFAULT_REPORT_TITLE`.  Sensor metadata and index formulas live under the
`resources/` directory.

Remaining hard-coded values are mostly cosmetic:

- Font family used for GIF annotations (`visualization/visualizer.py`)
- Example date ranges and output paths in the CLI help text

All index names, band mappings, reducers and scale parameters are now loaded
from configuration or resources.
