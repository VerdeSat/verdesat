"""
core.config
-----------

Configuration loader/manager for VerdeSat.  Provides a central API for
loading settings from YAML/TOML/JSON (or environment/CLI) and retrieving
them via `.get(...)`.
"""


class ConfigManager:
    """
    Loads and manages configuration from file, environment, CLI, or defaults.
    Provides a central entry point for parameterization and global options.
    """

    # Default supported vector input file extensions
    SUPPORTED_INPUT_FORMATS: tuple[str, ...] = (
        ".shp",
        ".geojson",
        ".gpkg",
        ".json",
        ".kml",
        ".kmz",
        ".gml",
    )

    # Default preset color palettes for visualizations
    PRESET_PALETTES: dict[str, tuple[str, ...]] = {
        "white-green": ("white", "green"),
        "red-white-green": ("red", "white", "green"),
        "brown-green": ("brown", "green"),
        "blue-white-green": ("blue", "white", "green"),
    }

    def __init__(self, config_path=None):
        self.config = {}  # Dict of all config params
        self.supported_input_formats = list(self.SUPPORTED_INPUT_FORMATS)
        self.preset_palettes = {k: list(v) for k, v in self.PRESET_PALETTES.items()}
        if config_path:
            self.load(config_path)

    def load(self, path):
        """Load configuration from a file (YAML/TOML/JSON)."""

    def get(self, key, default=None):
        """
        Retrieve a configuration value by key, or return `default` if not present.
        This method retrieves both config parameters and default attributes like
        `supported_input_formats` and `preset_palettes`.

        Args:
            key (str): The configuration parameter to look up.
            default:  The value to return if `key` is not found.
        """
        if key in self.config:
            return self.config.get(key, default)
        elif hasattr(self, key):
            return getattr(self, key)
        else:
            return default
