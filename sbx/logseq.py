#!/usr/bin/env python3
"""Plan a private, host-local Logseq MCP service, separate from the sbx gateway."""

import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def paths(home):
    home = Path(home)
    return (home / ".config/opencode-sbx/logseq.json",
            home / ".local/state/opencode-sbx/logseq-token")


def profile(home, port=12320):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid local port.")
    _, token = paths(home)
    return {"url": f"http://host.docker.internal:{port}/mcp/", "tokenFile": str(token)}


def initialize(home, port=12320, apply=False):
    connection, token = paths(home)
    value = profile(home, port)
    for path in (connection, token):
        if path.exists() or path.is_symlink():
            raise ValueError("Logseq state already exists; refusing to replace it.")
    if apply:
        created = []
        try:
            for path, content in (
                (token, secrets.token_urlsafe(48) + "\n"),
                (connection, json.dumps(value, indent=2) + "\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                    created.append(path)
                    stream.write(content)
        except Exception:
            for path in reversed(created):
                path.unlink()
            raise
    return {"connectionFile": str(connection), "connection": value,
            "tokenFile": str(token), "tokenContent": "<generated random MCP token, mode 0600>"}


def connection(home, workspace=None):
    connection_path, token_path = paths(home)
    if not connection_path.exists():
        return None
    if workspace is not None:
        root = Path(workspace).resolve()
        if any(path.resolve().is_relative_to(root) for path in (connection_path, token_path)):
            raise ValueError("Private Logseq state must be outside the workspace.")
    value = json.loads(connection_path.read_text())
    if not isinstance(value, dict) or set(value) != {"url", "tokenFile"}:
        raise ValueError("Invalid Logseq connection profile.")
    url = urlsplit(value["url"])
    if (url.scheme != "http" or url.hostname != "host.docker.internal"
            or url.path != "/mcp/" or url.query or url.fragment or url.username
            or url.password or not url.port or not 1024 <= url.port <= 65535):
        raise ValueError("Logseq must use the reviewed host-local MCP endpoint.")
    if value["tokenFile"] != str(token_path) or token_path.is_symlink():
        raise ValueError("Unexpected Logseq MCP token path.")
    if token_path.stat().st_mode & 0o077 or token_path.stat().st_uid != os.getuid():
        raise ValueError("Logseq MCP token must be owned by this user, mode 0600.")
    token = token_path.read_text().strip()
    if len(token) < 32 or any(char.isspace() for char in token):
        raise ValueError("Invalid Logseq MCP token.")
    return {"type": "remote", "url": value["url"], "oauth": False,
            "headers": {"Authorization": f"Bearer {token}"}}


def server_process(home, environ):
    remote = connection(home)
    if remote is None:
        raise ValueError("Initialize the private Logseq connection first.")
    config = json.loads((Path(home) / ".config/opencode/opencode.json").read_text())
    server = config.get("mcp", {}).get("servers", {}).get("logseq", {})
    command = [str(Path(home) / ".local/bin/mcp-logseq")]
    if server.get("type") != "local" or server.get("command") != command or server.get("disabled", False):
        raise ValueError("Unexpected host Logseq command.")
    settings = server.get("environment", {})
    if set(settings) != {"LOGSEQ_API_URL", "LOGSEQ_API_TOKEN"}:
        raise ValueError("Unexpected host Logseq environment.")
    api = urlsplit(settings["LOGSEQ_API_URL"])
    if api.scheme not in ("http", "https") or api.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Logseq API must remain local to the host.")
    if not settings["LOGSEQ_API_TOKEN"] or settings["LOGSEQ_API_TOKEN"].startswith("{env:"):
        raise ValueError("A resolved host Logseq API token is required.")
    env = {key: environ[key] for key in ("PATH", "HOME", "USER", "LANG", "TMPDIR") if key in environ}
    env.update(settings)
    env["HOME"] = str(home)
    env["MCP_HTTP_AUTH_TOKEN"] = remote["headers"]["Authorization"].removeprefix("Bearer ")
    command += ["--transport", "http", "--host", "127.0.0.1",
                "--port", str(urlsplit(remote["url"]).port)]
    return command, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="run the initialized host-local MCP service")
    parser.add_argument("--port", type=int, default=12320)
    parser.add_argument("--apply", action="store_true", help="create private connection state")
    args = parser.parse_args()
    try:
        if args.serve:
            if args.apply:
                raise ValueError("Initialization and serving are separate operations.")
            command, env = server_process(Path.home(), os.environ)
            os.execve(command[0], command, env)
        else:
            print(json.dumps(initialize(Path.home(), args.port, args.apply), indent=2))
    except (OSError, ValueError, TypeError, AttributeError):
        parser.exit(1, "Cannot configure Logseq. Review the private profile, file permissions and host settings.\n")


if __name__ == "__main__":
    main()
