"""Configuration loading utilities for aerospace services.

This module provides a unified interface for loading configuration from
TOML and YAML files. Each microservice in the project uses a different
config format to demonstrate proficiency with all three:

  - Portal service:    config.toml  (TOML)
  - GCS service:       config.yaml  (YAML)
  - Simulation:        config.json  (JSON — handled by Python's built-in json module)

WHY TOML?
---------
TOML (Tom's Obvious Minimal Language) is the standard for Python project
configuration (pyproject.toml, Cargo.toml for Rust). Built into Python 3.11+
via the `tomllib` module.

Advantages:
  - Simple, human-readable syntax
  - Strong typing (strings, integers, floats, booleans, dates)
  - No ambiguity (unlike YAML's implicit type coercion)
  - Native to Python ecosystem (PEP 680)

WHY YAML?
---------
YAML (YAML Ain't Markup Language) is the de facto standard for:
  - Kubernetes manifests (k8s/*.yaml)
  - Docker Compose / Podman Compose files
  - Ansible playbooks, CI/CD pipelines (GitHub Actions)

Advantages:
  - Very human-readable, minimal syntax
  - Supports complex nested structures
  - Comments (unlike JSON)
  - Widely used in DevOps and infrastructure

Disadvantages:
  - Implicit type coercion ("yes" → True, "no" → False, "1.0" → float)
  - Whitespace-sensitive (indentation errors are silent bugs)
  - Multiple ways to represent the same data

DESIGN DECISIONS:
-----------------
1. `load_toml()` uses `tomllib` (Python 3.11+ built-in) — no external dependency
2. `load_yaml()` uses `pyyaml` with `SafeLoader` — prevents arbitrary code execution
3. Both return plain `dict[str, Any]` — no custom config objects to learn
4. `get_nested()` helper for safe deep key access without KeyError chains
5. Optional Pydantic model validation via `load_toml_as()` and `load_yaml_as()`

SECURITY NOTE:
--------------
YAML has a known security risk: `yaml.load()` with the default `Loader` can
execute arbitrary Python code embedded in YAML files. We ALWAYS use
`yaml.safe_load()` (or `Loader=SafeLoader`) which only allows basic types:
  - str, int, float, bool, None
  - list, dict
  - datetime (ISO 8601)

Example:
    >>> from piasecki_common.config import load_toml, load_yaml, get_nested
    >>>
    >>> # Load TOML configuration
    >>> portal_config = load_toml("services/portal/config.toml")
    >>> portal_config["service"]["name"]
    'Portal'
    >>>
    >>> # Load YAML configuration
    >>> gcs_config = load_yaml("services/gcs/config.yaml")
    >>> gcs_config["redis"]["host"]
    'localhost'
    >>>
    >>> # Safe nested access (no KeyError if path doesn't exist)
    >>> get_nested(portal_config, "service", "name")
    'Portal'
    >>> get_nested(portal_config, "missing", "key", default="fallback")
    'fallback'
"""

import json
import tomllib
from pathlib import Path
from typing import Any, Type, TypeVar

import yaml
from pydantic import BaseModel

# Type variable for generic Pydantic model validation
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# TOML Configuration
# =============================================================================


def load_toml(filepath: Path | str) -> dict[str, Any]:
    """Load a TOML configuration file into a Python dictionary.

    Uses Python's built-in `tomllib` module (available since Python 3.11).
    TOML is the standard config format for Python projects (pyproject.toml).

    TOML Syntax Quick Reference:
        [section]           → dict key
        key = "value"       → string
        port = 8080         → integer
        enabled = true      → boolean
        rate = 10.5         → float
        tags = ["a", "b"]   → list

    Args:
        filepath: Path to the .toml file

    Returns:
        Dictionary with the parsed TOML contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        tomllib.TOMLDecodeError: If the file has invalid TOML syntax

    Example:
        >>> config = load_toml("services/portal/config.toml")
        >>> config["service"]["name"]
        'Portal'
        >>> config["service"]["port"]
        8080
    """
    filepath = Path(filepath)

    # tomllib requires binary mode ("rb") — this is a design choice by the
    # Python core team to avoid encoding ambiguity. TOML is always UTF-8.
    with open(filepath, "rb") as f:
        return tomllib.load(f)


def load_toml_as(filepath: Path | str, model: Type[T]) -> T:
    """Load TOML file and validate against a Pydantic model.

    Combines TOML parsing with Pydantic validation — if the config file
    is missing required fields or has wrong types, you get a clear error
    at startup rather than a mysterious crash later.

    Args:
        filepath: Path to the .toml file
        model: Pydantic model class to validate against

    Returns:
        Validated Pydantic model instance

    Raises:
        FileNotFoundError: If the file doesn't exist
        tomllib.TOMLDecodeError: If invalid TOML
        ValidationError: If the data doesn't match the model schema

    Example:
        >>> from pydantic import BaseModel
        >>> class ServiceConfig(BaseModel):
        ...     name: str
        ...     port: int
        ...     debug: bool = False
        >>>
        >>> config = load_toml_as("config.toml", ServiceConfig)
        >>> config.port
        8080
    """
    data = load_toml(filepath)
    return model.model_validate(data)


# =============================================================================
# YAML Configuration
# =============================================================================


def load_yaml(filepath: Path | str) -> dict[str, Any]:
    """Load a YAML configuration file into a Python dictionary.

    Uses `yaml.safe_load()` to prevent arbitrary code execution — this is
    critical for security. Never use `yaml.load()` with untrusted input.

    YAML Syntax Quick Reference:
        section:              → dict key
          key: value          → string (indentation = nesting)
          port: 8080          → integer
          enabled: true       → boolean
          rate: 10.5          → float
          tags:               → list
            - item1
            - item2

    YAML Gotchas:
        - "yes", "no", "on", "off" are parsed as booleans (True/False)
        - Norway's country code "NO" becomes False
        - Use quotes to force strings: "yes", "no", "NO"
        - Indentation must be spaces, never tabs

    Args:
        filepath: Path to the .yaml or .yml file

    Returns:
        Dictionary with the parsed YAML contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file has invalid YAML syntax

    Example:
        >>> config = load_yaml("services/gcs/config.yaml")
        >>> config["redis"]["host"]
        'localhost'
        >>> config["redis"]["port"]
        6379
    """
    filepath = Path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        # safe_load() only allows basic Python types (str, int, float, bool,
        # list, dict, None, datetime). It will NOT execute arbitrary Python
        # code that could be embedded in a malicious YAML file.
        data = yaml.safe_load(f)

    # yaml.safe_load() returns None for empty files — normalize to empty dict
    if data is None:
        return {}

    return data


def load_yaml_as(filepath: Path | str, model: Type[T]) -> T:
    """Load YAML file and validate against a Pydantic model.

    Combines YAML parsing with Pydantic validation for type-safe
    configuration loading.

    Args:
        filepath: Path to the .yaml or .yml file
        model: Pydantic model class to validate against

    Returns:
        Validated Pydantic model instance

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If invalid YAML
        ValidationError: If the data doesn't match the model schema

    Example:
        >>> from pydantic import BaseModel
        >>> class RedisConfig(BaseModel):
        ...     host: str = "localhost"
        ...     port: int = 6379
        ...     db: int = 0
        >>>
        >>> config = load_yaml_as("config.yaml", RedisConfig)
        >>> config.host
        'localhost'
    """
    data = load_yaml(filepath)
    return model.model_validate(data)


# =============================================================================
# JSON Configuration
# =============================================================================


def load_json(filepath: Path | str) -> dict[str, Any]:
    """Load a JSON configuration file into a Python dictionary.

    JSON is the simplest config format — no comments, strict syntax, but
    universally supported. Used by the simulation service for parameters
    that may change frequently.

    Args:
        filepath: Path to the .json file

    Returns:
        Dictionary with the parsed JSON contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file has invalid JSON syntax

    Example:
        >>> config = load_json("services/simulation/config.json")
        >>> config["update_rate_hz"]
        50
    """
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8")
    return json.loads(text)


def load_json_as(filepath: Path | str, model: Type[T]) -> T:
    """Load JSON file and validate against a Pydantic model.

    Args:
        filepath: Path to the .json file
        model: Pydantic model class to validate against

    Returns:
        Validated Pydantic model instance

    Example:
        >>> from pydantic import BaseModel
        >>> class SimConfig(BaseModel):
        ...     update_rate_hz: int = 50
        ...     noise_level: float = 0.01
        >>>
        >>> config = load_json_as("config.json", SimConfig)
    """
    data = load_json(filepath)
    return model.model_validate(data)


# =============================================================================
# Utility Helpers
# =============================================================================


def get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely access nested dictionary keys without KeyError chains.

    In configuration files, values are often deeply nested:
        config["database"]["connection"]["pool"]["max_size"]

    If any key is missing, Python raises KeyError. This helper returns a
    default value instead, similar to dict.get() but for nested access.

    Args:
        data: The dictionary to search
        *keys: Sequence of keys to traverse (one per nesting level)
        default: Value to return if any key is missing (default: None)

    Returns:
        The value at the nested path, or `default` if not found

    Example:
        >>> config = {"database": {"host": "localhost", "port": 5432}}
        >>> get_nested(config, "database", "host")
        'localhost'
        >>> get_nested(config, "database", "missing_key", default="N/A")
        'N/A'
        >>> get_nested(config, "nonexistent", "deep", "path", default=0)
        0
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def merge_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge multiple configuration dictionaries (left to right).

    Later dictionaries override earlier ones. Nested dicts are merged
    recursively rather than replaced entirely. This is useful for
    layered configuration:

        base config → environment overrides → CLI overrides

    Args:
        *configs: Dictionaries to merge (first = lowest priority)

    Returns:
        New merged dictionary (inputs are not modified)

    Example:
        >>> base = {"db": {"host": "localhost", "port": 5432}, "debug": False}
        >>> override = {"db": {"host": "prod-server"}, "debug": True}
        >>> merge_configs(base, override)
        {'db': {'host': 'prod-server', 'port': 5432}, 'debug': True}
    """
    result: dict[str, Any] = {}

    for config in configs:
        for key, value in config.items():
            # If both the existing and new values are dicts, merge recursively
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = merge_configs(result[key], value)
            else:
                result[key] = value

    return result
