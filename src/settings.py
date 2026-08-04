"""
Silicon Frontier Settings — LLM configuration with layered resolution.

Priority order (highest to lowest):
  1. Explicit arguments passed at call time
  2. Environment variables: SILICON_FRONTIER_LLM_BASE_URL, SILICON_FRONTIER_LLM_MODEL
  3. settings.json beside the packaged executable or in the project root
  4. Persistent per-user settings.json in the Windows local application-data folder
  5. Hardcoded defaults

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
from typing import Any, cast

# ---------------------------------------------------------------------------
# Defaults (used when nothing else provides a value)
# ---------------------------------------------------------------------------
DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LLM_MODEL = "local-model"

# Neutral starting point for a relationship that hasn't been established yet.
DEFAULT_RELATIONSHIP_TRUST = 50
DEFAULT_RELATIONSHIP_AFFINITY = 50

# Where to look for the settings file — project root (one level above src/)
_SETTINGS_FILE_NAME = "settings.json"
_APP_SETTINGS_DIR_NAME = "SiliconFrontier"


def user_settings_file() -> Path:
    """Return the persistent, per-user settings file location.

    Packaged builds are routinely replaced during an update, so settings must
    not live inside the ``dist`` directory.  ``LOCALAPPDATA`` is the normal
    Windows location for application-owned local configuration.  The fallback
    keeps source-tree use portable on platforms without that variable.
    """
    base = os.environ.get("SILICON_FRONTIER_SETTINGS_DIR") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / _APP_SETTINGS_DIR_NAME / _SETTINGS_FILE_NAME
    return Path.home() / ".silicon_frontier" / _SETTINGS_FILE_NAME


def _find_legacy_settings_file() -> Path | None:
    """Find the former project/bundle-local settings file, if present."""
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


def _find_settings_file() -> Path | None:
    """Prefer settings beside the executable, then use the per-user fallback."""
    local = _find_legacy_settings_file()
    if local is not None:
        return local
    persistent = user_settings_file()
    return persistent if persistent.is_file() else None


def load_settings() -> dict[str, Any]:
    """Load settings from the executable folder or per-user fallback.

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


def _resolve_str(
    explicit_value: str | None,
    env_var: str,
    settings_key: str,
    default: str | None
) -> str | None:
    """Shared layered resolution for string-valued settings.

    Priority: explicit (verbatim) > env var (verbatim) > settings.json (stripped) > default.
    """
    if explicit_value:
        return explicit_value

    env_val = os.environ.get(env_var)
    if env_val:
        return env_val

    settings = load_settings()
    val = settings.get(settings_key)
    if isinstance(val, str) and val.strip():
        return val.strip()

    return default


def _resolve_typed(
    explicit_value: Any,
    env_var: str,
    settings_key: str,
    default: Any,
    coerce: Any,
    validate: Any = None
) -> Any:
    """Shared layered resolution for numeric-valued settings.

    Priority: explicit (verbatim, unvalidated) > env var (coerced + validated)
    > settings.json (coerced + validated) > default. `validate` may return
    None to reject a value and fall through to the next priority level
    (e.g. an out-of-range port), or return a transformed value (e.g. a
    clamped minimum).
    """
    if explicit_value is not None:
        return coerce(explicit_value)

    env_val = os.environ.get(env_var)
    if env_val:
        try:
            value = coerce(env_val)
        except ValueError:
            pass
        else:
            if validate is not None:
                value = validate(value)
            if value is not None:
                return value

    settings = load_settings()
    val = settings.get(settings_key)
    if isinstance(val, (int, float)):
        value = coerce(val)
        if validate is not None:
            value = validate(value)
        if value is not None:
            return value

    return default


def get_llm_base_url(explicit_value: str | None = None) -> str:
    """Resolve the LLM base URL with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_LLM_BASE_URL", "llm_base_url", DEFAULT_LLM_BASE_URL))


def get_llm_model(explicit_value: str | None = None) -> str:
    """Resolve the LLM model name with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_LLM_MODEL", "llm_model", DEFAULT_LLM_MODEL))


def get_social_critic_base_url(explicit_value: str | None = None) -> str:
    """Resolve the optional endpoint used for social-witness evaluations."""
    return cast(str, _resolve_str(
        explicit_value,
        "SILICON_FRONTIER_SOCIAL_CRITIC_BASE_URL",
        "social_critic_base_url",
        get_llm_base_url(),
    ))


def get_social_critic_model(explicit_value: str | None = None) -> str:
    """Resolve the optional model used for social-witness evaluations."""
    return cast(str, _resolve_str(
        explicit_value,
        "SILICON_FRONTIER_SOCIAL_CRITIC_MODEL",
        "social_critic_model",
        get_llm_model(),
    ))


def get_social_critic_max_workers(explicit_value: int | None = None) -> int:
    """Resolve the bounded concurrent witness-evaluation worker count."""
    return _resolve_typed(
        explicit_value,
        "SILICON_FRONTIER_SOCIAL_CRITIC_MAX_WORKERS",
        "social_critic_max_workers",
        4,
        coerce=int,
        validate=lambda value: max(1, value),
    )


def get_strategic_reasoning_base_url(explicit_value: str | None = None) -> str:
    """Resolve the optional slow-planning endpoint for agent strategy reviews."""
    return cast(str, _resolve_str(
        explicit_value,
        "SILICON_FRONTIER_STRATEGIC_REASONING_BASE_URL",
        "strategic_reasoning_base_url",
        get_llm_base_url(),
    ))


def get_strategic_reasoning_model(explicit_value: str | None = None) -> str:
    """Resolve the model used only for periodic strategic planning."""
    return cast(str, _resolve_str(
        explicit_value,
        "SILICON_FRONTIER_STRATEGIC_REASONING_MODEL",
        "strategic_reasoning_model",
        get_llm_model(),
    ))


def get_strategic_review_interval(explicit_value: int | None = None) -> int:
    """Resolve how often every agent receives a strategic review."""
    return _resolve_typed(
        explicit_value,
        "SILICON_FRONTIER_STRATEGIC_REVIEW_INTERVAL",
        "strategic_review_interval",
        6,
        coerce=int,
        validate=lambda value: max(1, value),
    )


def get_strategic_max_workers(explicit_value: int | None = None) -> int:
    """Resolve the bounded concurrency for independent strategic reviews."""
    return _resolve_typed(
        explicit_value,
        "SILICON_FRONTIER_STRATEGIC_MAX_WORKERS",
        "strategic_max_workers",
        2,
        coerce=int,
        validate=lambda value: max(1, value),
    )


def get_api_key(explicit_value: str | None = None) -> str:
    """Resolve the API key with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_API_KEY", "api_key", "not-needed"))


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
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_REFLECTION_INTERVAL", "reflection_interval", 5,
        coerce=int, validate=lambda v: max(1, v)
    )


def get_delay_seconds(explicit_value: float | None = None) -> float:
    """Resolve the delay between cycles with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_DELAY_SECONDS", "delay_seconds", 0.3,
        coerce=float, validate=lambda v: max(0.0, v)
    )


def get_llm_timeout_seconds(explicit_value: float | None = None) -> float:
    """Resolve the per-request LLM call timeout with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_LLM_TIMEOUT_SECONDS", "llm_timeout_seconds", 60.0,
        coerce=float, validate=lambda v: max(0.0, v)
    )


def get_rounds(explicit_value: int | None = None) -> int:
    """Resolve the number of simulation rounds with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_ROUNDS", "rounds", 10,
        coerce=int, validate=lambda v: max(1, v)
    )


def get_random_seed(explicit_value: int | None = None) -> int | None:
    """Resolve the RNG seed for reproducible turn order, with layered priority.

    Returns None (unseeded) unless a seed is explicitly configured.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_RANDOM_SEED", "random_seed", None,
        coerce=int
    )


def get_config_dir(explicit_value: str | None = None) -> str:
    """Resolve the scenario config directory with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_CONFIG_DIR", "config_dir", "scenarios/default"))


def get_log_file(explicit_value: str | None = None) -> str | None:
    """Resolve the optional log file path with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return _resolve_str(explicit_value, "SILICON_FRONTIER_LOG_FILE", "log_file", None)


def get_dashboard_port(explicit_value: int | None = None) -> int:
    """Resolve the Streamlit dashboard port with layered priority.

    Args:
        explicit_value: If provided, used verbatim (highest priority).
    """
    return _resolve_typed(
        explicit_value, "SILICON_FRONTIER_DASHBOARD_PORT", "dashboard_port", 8501,
        coerce=int, validate=lambda v: v if 1 <= v <= 65535 else None
    )


def get_dashboard_host(explicit_value: str | None = None) -> str:
    """Resolve the Streamlit dashboard host with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_DASHBOARD_HOST", "dashboard_host", "localhost"))


def get_log_level(explicit_value: str | None = None) -> str:
    """Resolve the logging level with layered priority.

    Args:
        explicit_value: If provided and non-empty, used verbatim (highest priority).
    """
    return cast(str, _resolve_str(explicit_value, "SILICON_FRONTIER_LOG_LEVEL", "log_level", "INFO")).upper()


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
