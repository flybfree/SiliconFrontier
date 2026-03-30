"""
Windows launcher used for packaged builds.
"""

from __future__ import annotations

import os
import runpy
import sys

from src.app_paths import data_path, ensure_runtime_dirs, resource_path


def _launch_streamlit(script_name: str) -> int:
    from streamlit.web.cli import main as streamlit_main

    script_path = resource_path(script_name)
    sys.argv = [
        "streamlit",
        "run",
        str(script_path),
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]
    return streamlit_main()


def _launch_cli(args: list[str]) -> None:
    script_path = resource_path("run_simulation.py")
    sys.argv = [str(script_path), *args]
    runpy.run_path(str(script_path), run_name="__main__")


def main() -> int:
    ensure_runtime_dirs()
    os.chdir(data_path())

    args = sys.argv[1:]
    if args and args[0] in {"editor", "--editor"}:
        return _launch_streamlit("scenario_editor.py")
    if args and args[0] in {"cli", "--cli"}:
        _launch_cli(args[1:])
        return 0
    return _launch_streamlit("dashboard.py")


if __name__ == "__main__":
    raise SystemExit(main())
