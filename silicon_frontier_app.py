"""
Windows launcher used for packaged builds.
"""

from __future__ import annotations

import os
import runpy
import socket
import sys

from src.app_paths import data_path, ensure_runtime_dirs, resource_path

DEFAULT_STREAMLIT_PORT = 8501
MAX_STREAMLIT_PORT = 8510


def _find_available_port(start: int = DEFAULT_STREAMLIT_PORT, end: int = MAX_STREAMLIT_PORT) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No open localhost port found in range {start}-{end}.")


def _launch_streamlit(script_name: str) -> int:
    from streamlit.web.cli import main as streamlit_main

    script_path = resource_path(script_name)
    port = _find_available_port()
    app_url = f"http://localhost:{port}"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    print(f"Launching Streamlit app: {app_url}")
    sys.argv = [
        "streamlit",
        "run",
        str(script_path),
        "--global.developmentMode=false",
        "--server.port",
        str(port),
        "--server.address",
        "localhost",
        "--browser.serverAddress",
        "localhost",
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
