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

    def __init__(self, config_path=None):
        self.config = {}  # Dict of all config params
        if config_path:
            self.load(config_path)

    def load(self, path):
        """Load configuration from a file (YAML/TOML/JSON)."""
        pass

    def get(self, key, default=None):
        """
        Retrieve a configuration value by key, or return `default` if not present.

        Args:
            key (str): The configuration parameter to look up.
            default:  The value to return if `key` is not found.
        """
        return self.config.get(key, default)


# Supported vector file extensions for input
SUPPORTED_INPUT_FORMATS = [
    ".shp",
    ".geojson",
    ".gpkg",  # GeoPackage
    ".json",  # generic GeoJSON with .json extension
    ".kml",  # Keyhole Markup Language
    ".kmz",  # zipped KML
    ".gml",  # Geography Markup Language
]

PRESET_PALETTES = {
    "white-green": ["white", "green"],
    "red-white-green": ["red", "white", "green"],
    "brown-green": ["brown", "green"],
    "blue-white-green": ["blue", "white", "green"],
}
