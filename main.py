"""TBMCP entry point.

Usage:
  python main.py                     # Runs BOTH simultaneously (Default Mode)
  python main.py both                # Explicitly runs both concurrently
  python main.py mcp                 # MCP server (stdio) only for the AI client
  python main.py ui                  # Falcon web dashboard only for a human
  python main.py ui --debug          # Dashboard with DEBUG logs (symbol resolution, etc.)
"""
from __future__ import annotations

import os
import sys
import argparse
import logging
import multiprocessing

# Ensure the project folder is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from constants import DEFAULT_UI_PORT


def configure_logging(debug: bool) -> None:
    """Configure root logging. DEBUG level only with --debug; otherwise INFO.

    Logs go to stderr so they never corrupt the MCP server's stdout JSON-RPC stream.
    Sets the level explicitly (basicConfig is idempotent and would otherwise ignore a
    later call), and only attaches a handler if none exists yet.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        root.addHandler(handler)


def run_mcp(debug: bool = False) -> None:
    # Route all telemetry logs to stderr so they don't corrupt the stdout JSON-RPC line
    configure_logging(debug)
    from mcp.server import mcp
    mcp.stdio()


def run_ui(host: str, port: int, reload: bool = False, debug: bool = False) -> None:
    configure_logging(debug)
    from api.app import build_app
    build_app(host, port, reload=reload)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="tbmcp",
        description="Trading-data MCP server + web UI (Upstox-backed).",
    )
    sub = parser.add_subparsers(dest="command")
    
    # Define subcommands
    mcp_parser = sub.add_parser("mcp", help="Run the MCP server (stdio) only for AI clients.")
    mcp_parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logs.")

    ui_parser = sub.add_parser("ui", help="Run the Falcon web dashboard only for humans.")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    ui_parser.add_argument("--reload", action="store_true")
    ui_parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logs (shows symbol resolution).")

    both_parser = sub.add_parser("both", help="Run both the MCP server and Web UI concurrently (Default).")
    both_parser.add_argument("--host", default="127.0.0.1")
    both_parser.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    both_parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logs.")

    args = parser.parse_args(argv)

    # If no subcommand is passed, default to 'both' with default network values
    command = args.command or "both"
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", DEFAULT_UI_PORT)
    reload = getattr(args, "reload", False)

    # Execution routing block
    debug = getattr(args, "debug", False)
    if command == "ui":
        run_ui(host, port, reload, debug)
        
    elif command == "mcp":
        run_mcp(debug)
        
    elif command == "both":
        # 1. Spin up Falcon UI as a separate background process
        ui_process = multiprocessing.Process(
            target=run_ui, 
            args=(host, port, False, debug),  # Reload must be False inside multiprocessing
            daemon=True
        )
        ui_process.start()
        
        # 2. Immediately execute the blocking STDIO handler on the main loop
        run_mcp()


if __name__ == "__main__":
    # Crucial safety configuration for Windows system runtimes and Nuitka binary packages
    multiprocessing.freeze_support()
    main()
