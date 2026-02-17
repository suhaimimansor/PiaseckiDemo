"""Unit tests for piasecki_common.config — Config loading utilities.

Tests cover:
  - TOML loading (load_toml, load_toml_as)
  - YAML loading (load_yaml, load_yaml_as)
  - JSON loading (load_json, load_json_as)
  - Nested key access (get_nested)
  - Deep config merging (merge_configs)
  - Error handling: missing files, invalid syntax, validation errors
  - YAML gotchas: boolean coercion, empty files

WHY THESE TESTS?
----------------
Configuration errors are among the most common causes of outages in
production systems. A mistyped key, a wrong type, or a missing section can
crash a service at startup. These tests ensure:

  1. All three formats parse correctly
  2. Pydantic validation catches schema mismatches
  3. Deep merging works for layered config (base + env + CLI)
  4. get_nested gracefully handles missing keys

RUN:
    pytest tests/test_config.py -v
"""

from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from piasecki_common.config import (
    get_nested,
    load_json,
    load_json_as,
    load_toml,
    load_toml_as,
    load_yaml,
    load_yaml_as,
    merge_configs,
)


# =============================================================================
# Pydantic models for validation tests
# =============================================================================


class ServiceConfig(BaseModel):
    """Sample config model for testing load_*_as() functions."""

    name: str
    port: int
    debug: bool = False


class DatabaseConfig(BaseModel):
    """Nested config model for testing."""

    host: str = "localhost"
    port: int = 5432
    database: str = "piasecki"


# =============================================================================
# TOML Loading Tests
# =============================================================================


class TestLoadToml:
    """Tests for load_toml() and load_toml_as()."""

    def test_basic_toml_loading(self, tmp_path: Path) -> None:
        """Load a simple TOML file with string, int, and bool values."""
        toml_content = """
[service]
name = "Portal"
port = 8080
debug = true
"""
        filepath = tmp_path / "config.toml"
        filepath.write_text(toml_content)
        config = load_toml(filepath)
        assert config["service"]["name"] == "Portal"
        assert config["service"]["port"] == 8080
        assert config["service"]["debug"] is True

    def test_toml_nested_sections(self, tmp_path: Path) -> None:
        """Load TOML with nested sections (tables)."""
        toml_content = """
[database]
host = "localhost"
port = 5432

[database.pool]
max_size = 10
min_size = 2
"""
        filepath = tmp_path / "nested.toml"
        filepath.write_text(toml_content)
        config = load_toml(filepath)
        assert config["database"]["host"] == "localhost"
        assert config["database"]["pool"]["max_size"] == 10

    def test_toml_arrays(self, tmp_path: Path) -> None:
        """TOML arrays are parsed as Python lists."""
        toml_content = """
tags = ["flight", "telemetry", "imu"]
ports = [8080, 8081, 8082]
"""
        filepath = tmp_path / "arrays.toml"
        filepath.write_text(toml_content)
        config = load_toml(filepath)
        assert config["tags"] == ["flight", "telemetry", "imu"]
        assert config["ports"] == [8080, 8081, 8082]

    def test_toml_file_not_found(self) -> None:
        """Missing TOML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_toml("/nonexistent/config.toml")

    def test_load_toml_as_valid(self, tmp_path: Path) -> None:
        """load_toml_as validates against a Pydantic model."""
        toml_content = """
name = "Portal"
port = 8080
debug = true
"""
        filepath = tmp_path / "service.toml"
        filepath.write_text(toml_content)
        config = load_toml_as(filepath, ServiceConfig)
        assert config.name == "Portal"
        assert config.port == 8080
        assert config.debug is True

    def test_load_toml_as_invalid(self, tmp_path: Path) -> None:
        """load_toml_as raises ValidationError for invalid data."""
        toml_content = """
name = "Portal"
# Missing required 'port' field
"""
        filepath = tmp_path / "bad.toml"
        filepath.write_text(toml_content)
        with pytest.raises(ValidationError):
            load_toml_as(filepath, ServiceConfig)

    def test_load_toml_as_with_defaults(self, tmp_path: Path) -> None:
        """Pydantic model default values fill in missing TOML fields."""
        toml_content = """
name = "GCS"
port = 9090
# debug is omitted — defaults to False
"""
        filepath = tmp_path / "defaults.toml"
        filepath.write_text(toml_content)
        config = load_toml_as(filepath, ServiceConfig)
        assert config.debug is False


# =============================================================================
# YAML Loading Tests
# =============================================================================


class TestLoadYaml:
    """Tests for load_yaml() and load_yaml_as()."""

    def test_basic_yaml_loading(self, tmp_path: Path) -> None:
        """Load a simple YAML file."""
        yaml_content = """
service:
  name: GCS
  port: 9090
  debug: false
"""
        filepath = tmp_path / "config.yaml"
        filepath.write_text(yaml_content)
        config = load_yaml(filepath)
        assert config["service"]["name"] == "GCS"
        assert config["service"]["port"] == 9090

    def test_yaml_nested_structures(self, tmp_path: Path) -> None:
        """YAML nested mappings are parsed as nested dicts."""
        yaml_content = """
redis:
  host: localhost
  port: 6379
  db: 0
  options:
    timeout: 30
    retry: true
"""
        filepath = tmp_path / "nested.yaml"
        filepath.write_text(yaml_content)
        config = load_yaml(filepath)
        assert config["redis"]["options"]["timeout"] == 30
        assert config["redis"]["options"]["retry"] is True

    def test_yaml_lists(self, tmp_path: Path) -> None:
        """YAML sequences are parsed as Python lists."""
        yaml_content = """
sensors:
  - imu
  - gps
  - airspeed
"""
        filepath = tmp_path / "lists.yaml"
        filepath.write_text(yaml_content)
        config = load_yaml(filepath)
        assert config["sensors"] == ["imu", "gps", "airspeed"]

    def test_yaml_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML file returns empty dict (not None)."""
        filepath = tmp_path / "empty.yaml"
        filepath.write_text("")
        config = load_yaml(filepath)
        assert config == {}

    def test_yaml_file_not_found(self) -> None:
        """Missing YAML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_yaml("/nonexistent/config.yaml")

    def test_load_yaml_as_valid(self, tmp_path: Path) -> None:
        """load_yaml_as validates against Pydantic model."""
        yaml_content = """
name: GCS
port: 9090
debug: true
"""
        filepath = tmp_path / "service.yaml"
        filepath.write_text(yaml_content)
        config = load_yaml_as(filepath, ServiceConfig)
        assert config.name == "GCS"
        assert config.port == 9090
        assert config.debug is True

    def test_load_yaml_as_invalid(self, tmp_path: Path) -> None:
        """load_yaml_as raises ValidationError for bad data."""
        yaml_content = """
name: GCS
port: "not_a_number"
"""
        filepath = tmp_path / "bad.yaml"
        filepath.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_yaml_as(filepath, ServiceConfig)


# =============================================================================
# JSON Loading Tests
# =============================================================================


class TestLoadJson:
    """Tests for load_json() and load_json_as()."""

    def test_basic_json_loading(self, tmp_path: Path) -> None:
        """Load a simple JSON config file."""
        import json

        data = {"update_rate_hz": 50, "noise_level": 0.01, "enabled": True}
        filepath = tmp_path / "config.json"
        filepath.write_text(json.dumps(data))
        config = load_json(filepath)
        assert config["update_rate_hz"] == 50
        assert config["noise_level"] == 0.01

    def test_json_nested(self, tmp_path: Path) -> None:
        """Nested JSON objects are parsed as nested dicts."""
        import json

        data = {"simulation": {"physics": {"gravity": 9.81, "drag": 0.5}}}
        filepath = tmp_path / "nested.json"
        filepath.write_text(json.dumps(data))
        config = load_json(filepath)
        assert config["simulation"]["physics"]["gravity"] == 9.81

    def test_json_file_not_found(self) -> None:
        """Missing JSON file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_json("/nonexistent/config.json")

    def test_load_json_as_valid(self, tmp_path: Path) -> None:
        """load_json_as validates against a Pydantic model."""
        import json

        data = {"name": "Simulation", "port": 7070}
        filepath = tmp_path / "service.json"
        filepath.write_text(json.dumps(data))
        config = load_json_as(filepath, ServiceConfig)
        assert config.name == "Simulation"
        assert config.port == 7070
        assert config.debug is False  # Default

    def test_load_json_as_invalid(self, tmp_path: Path) -> None:
        """load_json_as raises ValidationError for missing required fields."""
        import json

        data = {"debug": True}  # Missing name and port
        filepath = tmp_path / "bad.json"
        filepath.write_text(json.dumps(data))
        with pytest.raises(ValidationError):
            load_json_as(filepath, ServiceConfig)


# =============================================================================
# get_nested() Tests
# =============================================================================


class TestGetNested:
    """Tests for the get_nested() utility function."""

    def test_shallow_key(self) -> None:
        """Single-level key access."""
        data = {"name": "Portal", "port": 8080}
        assert get_nested(data, "name") == "Portal"

    def test_deep_key(self) -> None:
        """Multi-level nested key access."""
        data = {"database": {"connection": {"pool": {"max_size": 10}}}}
        assert get_nested(data, "database", "connection", "pool", "max_size") == 10

    def test_missing_key_returns_default(self) -> None:
        """Missing key returns default value (None by default)."""
        data = {"a": {"b": 1}}
        assert get_nested(data, "a", "missing") is None

    def test_missing_key_custom_default(self) -> None:
        """Custom default value is returned for missing keys."""
        data = {"a": 1}
        assert get_nested(data, "x", "y", "z", default="fallback") == "fallback"

    def test_empty_dict(self) -> None:
        """Empty dict always returns default."""
        assert get_nested({}, "any", "key", default=42) == 42

    def test_intermediate_non_dict(self) -> None:
        """If an intermediate value is not a dict, return default."""
        data = {"a": "not_a_dict"}
        assert get_nested(data, "a", "b", default="nope") == "nope"

    def test_no_keys_returns_entire_dict(self) -> None:
        """With no keys, returns the dict itself."""
        data = {"a": 1}
        assert get_nested(data) == data

    def test_numeric_default(self) -> None:
        """Default can be any type: int, float, list, etc."""
        data = {"x": 1}
        assert get_nested(data, "missing", default=0) == 0
        assert get_nested(data, "missing", default=[]) == []


# =============================================================================
# merge_configs() Tests
# =============================================================================


class TestMergeConfigs:
    """Tests for the merge_configs() deep-merge utility."""

    def test_simple_merge(self) -> None:
        """Non-overlapping dicts are merged."""
        a = {"host": "localhost"}
        b = {"port": 5432}
        result = merge_configs(a, b)
        assert result == {"host": "localhost", "port": 5432}

    def test_override(self) -> None:
        """Later values override earlier ones."""
        base = {"debug": False, "host": "localhost"}
        override = {"debug": True}
        result = merge_configs(base, override)
        assert result["debug"] is True
        assert result["host"] == "localhost"

    def test_deep_merge(self) -> None:
        """Nested dicts are merged recursively, not replaced."""
        base = {"db": {"host": "localhost", "port": 5432}, "debug": False}
        override = {"db": {"host": "prod-server"}, "debug": True}
        result = merge_configs(base, override)
        # db.host is overridden, but db.port is preserved
        assert result == {"db": {"host": "prod-server", "port": 5432}, "debug": True}

    def test_three_way_merge(self) -> None:
        """Three configs merged left-to-right (last wins)."""
        base = {"a": 1, "b": 2, "c": 3}
        env = {"a": 10, "d": 4}
        cli = {"a": 100}
        result = merge_configs(base, env, cli)
        assert result == {"a": 100, "b": 2, "c": 3, "d": 4}

    def test_empty_configs(self) -> None:
        """Merging with empty dicts is a no-op."""
        data = {"x": 1}
        assert merge_configs({}, data) == data
        assert merge_configs(data, {}) == data
        assert merge_configs({}, {}) == {}

    def test_inputs_not_mutated(self) -> None:
        """merge_configs does not modify the input dictionaries."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = merge_configs(base, override)
        # Original dicts unchanged
        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}
        # Result has both keys
        assert result == {"a": {"b": 1, "c": 2}}

    def test_non_dict_replaces_dict(self) -> None:
        """A non-dict value completely replaces a nested dict."""
        base = {"a": {"nested": True}}
        override = {"a": "flat_value"}
        result = merge_configs(base, override)
        assert result == {"a": "flat_value"}

    def test_no_configs(self) -> None:
        """Merging zero configs returns empty dict."""
        assert merge_configs() == {}
