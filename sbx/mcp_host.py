#!/usr/bin/env python3
"""Run the fixed host Browse executable with reviewed environment settings."""

import json
import os
from pathlib import Path
import sys


def browse_process(home, environ):
    """Do not execute commands or forward arbitrary environment from config."""
    home = Path(home)
    directory = home / ".config/opencode"
    if (directory / "opencode.jsonc").exists():
        raise ValueError("JSONC needs manual review.")
    config = json.loads((directory / "opencode.json").read_text())
    server = config.get("mcp", {}).get("servers", {}).get("browse", {})
    command = [str(home / ".local/bin/browse"), "mcp"]
    if (server.get("type") != "local" or server.get("command") != command
            or server.get("disabled", False)):
        raise ValueError("Host Browse configuration differs from the reviewed command.")
    settings = server.get("environment", {})
    if not isinstance(settings, dict) or set(settings) - {"OPENCODE_BROWSER_RUNTIME"}:
        raise ValueError("Unreviewed Browse environment settings.")
    runtime = settings.get("OPENCODE_BROWSER_RUNTIME")
    if runtime is not None and (not isinstance(runtime, str) or "\x00" in runtime):
        raise ValueError("Invalid Browse runtime.")
    # Keep the host user's relay discovery paths. Do not pass provider keys,
    # Logseq credentials, or environment inherited from the sandbox daemon.
    allowed = ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL",
               "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")
    env = {key: environ[key] for key in allowed if key in environ}
    env["HOME"] = str(home)
    if runtime is not None:
        env["OPENCODE_BROWSER_RUNTIME"] = runtime
    return command, env


def main():
    if sys.argv[1:] != ["browse"]:
        sys.exit("Only Browse is supported. Logseq must not use the shared gateway.")
    try:
        command, env = browse_process(Path.home(), os.environ)
    except (OSError, ValueError, TypeError, AttributeError):
        sys.exit("Cannot use the reviewed host Browse configuration.")
    # stdout belongs exclusively to the MCP stdio protocol.
    os.execve(command[0], command, env)


if __name__ == "__main__":
    main()
