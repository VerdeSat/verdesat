"""core.config
---------------

Configuration loader/manager for VerdeSat. Provides a central API for
loading settings from YAML/TOML/JSON (or environment/CLI) and retrieving
them via :py:meth:`ConfigManager.get`.
"""

# Imports for config parsing
import os
import json
import yaml
import toml


# Exception for config validation errors
class ConfigValidationError(Exception):
    """Raised when configuration loading or validation fails."""


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

    # Default spectral index and output column naming
    DEFAULT_INDEX: str = "ndvi"
    VALUE_COL_TEMPLATE: str = "mean_{index}"
    DEFAULT_REPORT_TITLE: str = "VerdeSat Report"

    def __init__(self, config_path=None):
        self.config = {
            "default_index": self.DEFAULT_INDEX,
            "value_col_template": self.VALUE_COL_TEMPLATE,
            "report_title": self.DEFAULT_REPORT_TITLE,
        }
        self.supported_input_formats = list(self.SUPPORTED_INPUT_FORMATS)
        self.preset_palettes = {k: list(v) for k, v in self.PRESET_PALETTES.items()}
        if config_path:
            self.load(config_path)

    def load(self, path: str) -> None:
        """
        Load configuration from a file (YAML, TOML, or JSON).
        Overwrites existing keys in self.config.
        """
        ext = os.path.splitext(path)[1].lower()
        try:
            with open(path, "r", encoding="utf-8") as f:
                if ext in (".yaml", ".yml"):
                    data = yaml.safe_load(f)
                elif ext == ".toml":
                    data = toml.load(f)
                elif ext == ".json":
                    data = json.load(f)
                else:
                    raise ConfigValidationError(f"Unsupported config format: {ext}")
        except Exception as e:
            raise ConfigValidationError(
                f"Failed to load config from {path}: {e}"
            ) from e
        if not isinstance(data, dict):
            raise ConfigValidationError(f"Config file {path} did not produce a dict")
        # Update internal config dict
        self.config.update(data)

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

    def merge(self, other: "ConfigManager") -> None:
        """
        Merge another ConfigManager into this one.
        Values in other.config override this.config.
        Also merges supported_input_formats and preset_palettes.
        """
        if not isinstance(other, ConfigManager):
            raise TypeError("Can only merge ConfigManager instances")
        # Merge base config
        self.config.update(other.config)
        # Merge list attributes
        self.supported_input_formats = list(
            dict.fromkeys(self.supported_input_formats + other.supported_input_formats)
        )
        # Merge palettes dict
        self.preset_palettes.update(other.preset_palettes)

    def get_value_col(self, index: str | None = None) -> str:
        """Return the value column name for a given index."""
        idx = index or self.get("default_index", self.DEFAULT_INDEX)
        template = self.get("value_col_template", self.VALUE_COL_TEMPLATE)
        return template.format(index=idx)

    def get_report_title(self) -> str:
        """Return the default report title from config."""
        return self.get("report_title", self.DEFAULT_REPORT_TITLE)
