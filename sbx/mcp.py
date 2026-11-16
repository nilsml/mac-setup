#!/usr/bin/env python3
"""Register approved public MCP services for all dynamic gateways."""

import argparse
import json
from pathlib import Path
import subprocess


DEFAULT_LAUNCHER = Path(__file__).resolve().parent
ROVO_URL = "https://mcp.atlassian.com/v2/mcp"


def browse_plan(launcher=DEFAULT_LAUNCHER):
    """Return commands without starting, registering, or modifying anything."""
    launcher = Path(launcher).expanduser()
    if not launcher.is_absolute():
        raise ValueError("Launcher path must be absolute.")
    launcher = launcher.resolve()
    commands = [
        ["sbx", "mcp", "add", "browse", "--command", "/usr/bin/python3",
         "--args", f"{launcher / 'mcp_host.py'},browse", "--dir", str(Path.home())],
    ]
    return commands


def registration_plan(service="browse", launcher=DEFAULT_LAUNCHER):
    if service not in ("browse", "rovo"):
        raise ValueError("Only public services belong in the shared gateway. Logseq is separate.")
    commands = browse_plan(launcher)
    if service == "rovo":
        commands[0] = ["sbx", "mcp", "add", "rovo", "--url", ROVO_URL, "--skip-auth"]
    return commands


def activate(service="browse", launcher=DEFAULT_LAUNCHER):
    """Explicit opt-in; refuse to replace any existing registration."""
    commands = registration_plan(service, launcher)
    runner = Path(launcher).expanduser().resolve() / "mcp_host.py"
    if service == "browse" and not runner.is_file():
        raise ValueError("Install the reviewed launcher before activation.")
    result = subprocess.run(
        ["sbx", "mcp", "ls", "--quiet"], check=True, capture_output=True, text=True,
    )
    if service in result.stdout.split():
        raise ValueError("Service already registered; inspect it manually before loading.")
    for command in commands:
        subprocess.run(command, check=True)


def activate_browse(launcher=DEFAULT_LAUNCHER):
    return activate("browse", launcher)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", nargs="?", choices=("browse", "rovo"), default="browse")
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.apply:
            activate(args.service, args.launcher)
        else:
            print(json.dumps(registration_plan(args.service, args.launcher), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError):
        parser.exit(1, "MCP activation failed. Inspect registration and target state before retrying.\n")


if __name__ == "__main__":
    main()
