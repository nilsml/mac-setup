"""Add a dedicated Logseq connection and native V2 permissions in a new sandbox."""

import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit


def rule(action, effect, resource="*"):
    return {"action": action, "resource": resource, "effect": effect}


def native_permissions():
    """The mounted Logseq agent owns its exceptions; do not duplicate its policy."""
    return [
        rule("logseq_*", "deny"),
        rule("opencode_list_mcp_resources", "deny", "logseq"),
        rule("opencode_read_mcp_resource", "deny", "logseq:*"),
    ]


def configure(home, remote):
    home = Path(home)
    if not isinstance(remote, dict) or set(remote) != {"type", "url", "oauth", "headers"}:
        raise ValueError("Unexpected Logseq remote configuration.")
    url = urlsplit(remote["url"])
    if (remote["type"] != "remote" or remote["oauth"] is not False
            or url.scheme != "http" or url.hostname != "host.docker.internal"
            or url.path != "/mcp/" or url.query or url.fragment or url.username
            or url.password or not url.port or not 1024 <= url.port <= 65535):
        raise ValueError("Unexpected Logseq endpoint.")
    headers = remote["headers"]
    if (not isinstance(headers, dict) or set(headers) != {"Authorization"}
            or not isinstance(headers["Authorization"], str)
            or not headers["Authorization"].startswith("Bearer ")
            or len(headers["Authorization"]) < 39
            or "\n" in headers["Authorization"] or "\r" in headers["Authorization"]):
        raise ValueError("Invalid Logseq MCP authorization.")
    root = home / ".config/opencode"
    path = root / "opencode.json"
    if (path.is_symlink() or root.is_symlink() or (home / ".config").is_symlink()
            or (root / "opencode.jsonc").exists()):
        raise ValueError("Competing or symlinked OpenCode configuration.")
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError("Invalid OpenCode configuration.")
    mcp = value.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise ValueError("Invalid MCP configuration.")
    # Docker may generate the legacy flat MCP shape. Normalize it once in this
    # new sandbox, preserving every existing server and credential reference.
    if "servers" not in mcp:
        if not all(isinstance(server, dict) and server.get("type") in ("remote", "local")
                   for server in mcp.values()):
            raise ValueError("Ambiguous legacy MCP configuration.")
        mcp = {"servers": mcp}
        value["mcp"] = mcp
    servers = mcp["servers"]
    if not isinstance(servers, dict):
        raise ValueError("Invalid MCP servers.")
    permissions = value.setdefault("permissions", [])
    if not isinstance(permissions, list):
        raise ValueError("Invalid native permission configuration.")
    shared = native_permissions()
    if "logseq" in servers:
        if servers["logseq"] == remote and permissions[-len(shared):] == shared:
            return False
        raise ValueError("An unrelated Logseq configuration already exists.")
    permissions.extend(shared)
    servers["logseq"] = remote
    # Publish connection and policy together. Never leave an unguarded connection
    # behind after validation errors or a partial write.
    root.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".opencode-mcp-", dir=root)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


if __name__ == "__main__":
    try:
        configure(Path.home(), json.load(sys.stdin))
    except (OSError, ValueError, TypeError, AttributeError):
        sys.exit("Logseq setup refused. Review native permissions and connection configuration.")
