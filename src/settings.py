"""
Silicon Frontier Settings — LLM configuration with layered resolution.

Priority order (highest to lowest):
  1. Explicit arguments passed at call time
  2. Environment variables: SILICON_FRONTIER_LLM_BASE_URL, SILICON_FRONTIER_LLM_MODEL
  3. settings.json in the project root directory
  4. Hardcoded defaults

The settings file is a JSON object with optional keys:
    {
        "llm_base_url": "http://localhost:1234/v1",
        "llm_model": "local-model"
    }
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults (used when nothing else provides a value)
# ---------------------------------------------------------------------------
DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LLM_MODEL = "local-model"

# Where to look for the settings file — project root (one level above src/)
_SETTINGS_FILE_NAME = "settings.json"


def _find_settings_file() -> Path | None:
    """Return the path to settings.json if it exists, else None.

    Walks upward from this module's location looking for the first match.
    """
    current = Path(__file__).resolve().parent  # src/
    while True:
        candidate = current / _SETTINGS_FILE_NAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_settings() -> dict[str, Any]:
    """Load settings from the JSON file (if present).

    Returns an empty dict when no settings file is found or it cannot be parsed.
    """
    path = _find_settings_file()
    if path is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def get_llm_base_url(explicit_value: str | None = None) -> str:
    """Resolve the LLM base URL with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_LLM_BASE_URL")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    file_url = settings.get("llm_base_url")
    if isinstance(file_url, str) and file_url.strip():
        return file_url.strip()

    return DEFAULT_LLM_BASE_URL


def get_llm_model(explicit_value: str | None = None) -> str:
    """Resolve the LLM model name with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_LLM_MODEL")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    file_model = settings.get("llm_model")
    if isinstance(file_model, str) and file_model.strip():
        return file_model.strip()

    return DEFAULT_LLM_MODEL


def get_api_key(explicit_value: str | None = None) -> str:
    """Resolve the API key with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_API_KEY")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    file_key = settings.get("api_key")
    if isinstance(file_key, str) and file_key.strip():
        return file_key.strip()

    return "not-needed"


def get_enable_structured_output(explicit_value: bool | None = None) -> bool:
    """Resolve the structured-output flag with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    if explicit_value is not None:
        return bool(explicit_value)

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_ENABLE_STRUCTURED_OUTPUT")
    if env_val:
        return env_val.lower() in ("1", "true", "yes", "on")

    # Settings file
    settings = load_settings()
    val = settings.get("enable_structured_output")
    if isinstance(val, bool):
        return val
    if isinstance(val, str) and val.strip().lower() in ("1", "true", "yes", "on"):
        return True

    return False


def get_reflection_interval(explicit_value: int | None = None) -> int:
    """Resolve the reflection interval with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    if explicit_value is not None:
        return int(explicit_value)

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_REFLECTION_INTERVAL")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass

    # Settings file
    settings = load_settings()
    val = settings.get("reflection_interval")
    if isinstance(val, (int, float)):
        return max(1, int(val))

    return 5


def get_delay_seconds(explicit_value: float | None = None) -> float:
    """Resolve the delay between cycles with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    if explicit_value is not None:
        return float(explicit_value)

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_DELAY_SECONDS")
    if env_val:
        try:
            return max(0.0, float(env_val))
        except ValueError:
            pass

    # Settings file
    settings = load_settings()
    val = settings.get("delay_seconds")
    if isinstance(val, (int, float)):
        return max(0.0, float(val))

    return 0.3


def get_rounds(explicit_value: int | None = None) -> int:
    """Resolve the number of simulation rounds with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    if explicit_value is not None:
        return int(explicit_value)

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_ROUNDS")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass

    # Settings file
    settings = load_settings()
    val = settings.get("rounds")
    if isinstance(val, (int, float)):
        return max(1, int(val))

    return 10


def get_config_dir(explicit_value: str | None = None) -> str:
    """Resolve the scenario config directory with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_CONFIG_DIR")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    val = settings.get("config_dir")
    if isinstance(val, str) and val.strip():
        return val.strip()

    return "scenarios/default"


def get_log_file(explicit_value: str | None = None) -> str | None:
    """Resolve the optional log file path with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_LOG_FILE")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    val = settings.get("log_file")
    if isinstance(val, str) and val.strip():
        return val.strip()

    return None


def get_dashboard_port(explicit_value: int | None = None) -> int:
    """Resolve the Streamlit dashboard port with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    if explicit_value is not None:
        return int(explicit_value)

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_DASHBOARD_PORT")
    if env_val:
        try:
            port = int(env_val)
            if 1 <= port <= 65535:
                return port
        except ValueError:
            pass

    # Settings file
    settings = load_settings()
    val = settings.get("dashboard_port")
    if isinstance(val, (int, float)):
        port = int(val)
        if 1 <= port <= 65535:
            return port

    return 8501


def get_dashboard_host(explicit_value: str | None = None) -> str:
    """Resolve the Streamlit dashboard host with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_DASHBOARD_HOST")
    if env_val:
        return env_val

    # Settings file
    settings = load_settings()
    val = settings.get("dashboard_host")
    if isinstance(val, str) and val.strip():
        return val.strip()

    return "localhost"


def get_log_level(explicit_value: str | None = None) -> str:
    """Resolve the logging level with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    if explicit_value:
        return explicit_value.upper()

    # Environment variable
    env_val = os.environ.get("SILICON_FRONTIER_LOG_LEVEL")
    if env_val:
        return env_val.upper()

    # Settings file
    settings = load_settings()
    val = settings.get("log_level")
    if isinstance(val, str) and val.strip():
        return val.strip().upper()

    return "INFO"


def get_all_settings() -> dict[str, Any]:
    """Return a flat dict of all resolved settings (lowest priority only).

    Useful for diagnostics — shows what the file/env vars actually contain.
    """
    settings = load_settings()
    return {
        "llm_base_url": settings.get("llm_base_url", DEFAULT_LLM_BASE_URL),
        "llm_model": settings.get("llm_model", DEFAULT_LLM_MODEL),
        "api_key": "<resolved from env or file>" if (os.environ.get("SILICON_FRONTIER_API_KEY") or load_settings().get("api_key")) else "not-needed",
        "enable_structured_output": get_enable_structured_output(),
        "reflection_interval": get_reflection_interval(),
        "delay_seconds": get_delay_seconds(),
        "rounds": get_rounds(),
        "config_dir": get_config_dir(),
        "log_file": get_log_file(),
        "dashboard_port": get_dashboard_port(),
        "dashboard_host": get_dashboard_host(),
        "log_level": get_log_level(),
    }
