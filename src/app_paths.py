"""
Helpers for locating bundled resources and writable runtime directories.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


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


def bootstrap_runtime() -> None:
    """Ensure runtime directories exist and make them the working directory."""
    ensure_runtime_dirs()
    os.chdir(data_path())


def atomic_write_json(path: Path, data: Any, *, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Write JSON to `path` atomically: write to a temp file in the same directory, then replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise
