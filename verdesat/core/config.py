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
