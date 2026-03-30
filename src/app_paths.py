"""
Helpers for locating bundled resources and writable runtime directories.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_root() -> Path:
    """Directory containing packaged resources."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def runtime_root() -> Path:
    """Directory the user interacts with at runtime."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_root()


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def data_path(*parts: str) -> Path:
    return runtime_root().joinpath(*parts)


def ensure_runtime_dirs() -> None:
    if is_frozen():
        for dirname in ("library", "scenarios"):
            source = resource_path(dirname)
            target = data_path(dirname)
            if source.exists() and not target.exists():
                shutil.copytree(source, target)
    for dirname in ("logs", "saves"):
        data_path(dirname).mkdir(parents=True, exist_ok=True)
