"""Test suite for ConfigManager: verifying loading formats, defaults, and merging behavior."""

import json
import pytest

import yaml
import toml

from verdesat.core.config import ConfigManager, ConfigValidationError


def test_load_json(tmp_path):
    """Ensure JSON files load correctly and default values are returned for missing keys."""
    cfg_file = tmp_path / "cfg.json"
    data = {"a": 1, "b": "two"}
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    cfg = ConfigManager()
    cfg.load(str(cfg_file))

    assert cfg.get("a") == 1
    assert cfg.get("b") == "two"
    # missing key uses default
    assert cfg.get("missing", "def") == "def"


def test_load_yaml(tmp_path):
    """Verify YAML files are parsed and values retrieved accurately."""
    cfg_file = tmp_path / "cfg.yaml"
    data = {"x": 3.14, "y": [1, 2, 3]}
    cfg_file.write_text(yaml.safe_dump(data), encoding="utf-8")

    cfg = ConfigManager()
    cfg.load(str(cfg_file))

    assert cfg.get("x") == pytest.approx(3.14)
    assert cfg.get("y") == [1, 2, 3]


def test_load_toml(tmp_path):
    """Check TOML file loading and value retrieval functionality."""
    cfg_file = tmp_path / "cfg.toml"
    data = {"foo": "bar", "num": 42}
    cfg_file.write_text(toml.dumps(data), encoding="utf-8")

    cfg = ConfigManager()
    cfg.load(str(cfg_file))

    assert cfg.get("foo") == "bar"
    assert cfg.get("num") == 42


def test_load_unsupported_extension(tmp_path):
    """Confirm that loading unsupported file extensions raises ConfigValidationError."""
    cfg_file = tmp_path / "cfg.txt"
    cfg_file.write_text("whatever", encoding="utf-8")

    cfg = ConfigManager()
    with pytest.raises(ConfigValidationError):
        cfg.load(str(cfg_file))


def test_load_invalid_content(tmp_path):
    """Ensure invalid JSON content triggers a ConfigValidationError."""
    # valid .json but invalid JSON content
    cfg_file = tmp_path / "bad.json"
    cfg_file.write_text("not a json!", encoding="utf-8")

    cfg = ConfigManager()
    with pytest.raises(ConfigValidationError):
        cfg.load(str(cfg_file))


def test_get_default_attrs():
    """Validate default attributes (supported_input_formats and preset_palettes) are present."""
    cfg = ConfigManager()
    # supported_input_formats and preset_palettes come from class defaults
    fmt_list = cfg.get("supported_input_formats")
    assert isinstance(fmt_list, list)
    assert ".shp" in fmt_list

    palettes = cfg.get("preset_palettes")
    assert isinstance(palettes, dict)
    assert "white-green" in palettes


def test_merge_configs():
    """Test merging two ConfigManager instances
    combines configs, formats, and palettes correctly."""
    cfg1 = ConfigManager()
    cfg1.config = {"a": 1}
    cfg1.supported_input_formats = [".a", ".b"]
    cfg1.preset_palettes = {"p1": ["red"]}

    cfg2 = ConfigManager()
    cfg2.config = {"b": 2}
    cfg2.supported_input_formats = [".b", ".c"]
    cfg2.preset_palettes = {"p2": ["blue"]}

    cfg1.merge(cfg2)

    # config keys merged, with latter override
    assert cfg1.get("a") == 1
    assert cfg1.get("b") == 2

    # formats merged uniquely, preserving order
    assert cfg1.supported_input_formats == [".a", ".b", ".c"]

    # palettes combined
    assert cfg1.preset_palettes["p1"] == ["red"]
    assert cfg1.preset_palettes["p2"] == ["blue"]


def test_merge_wrong_type():
    """Assert merging with a non-ConfigManager object raises a TypeError."""
    cfg = ConfigManager()
    with pytest.raises(TypeError):
        cfg.merge("not a config manager")
