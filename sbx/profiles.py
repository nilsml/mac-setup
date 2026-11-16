"""Read-only capability-layer selection. No installation or source execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


DEFAULT_CATALOG = Path.home() / ".config/opencode-sbx/catalog.json"


@dataclass(frozen=True)
class Layer:
    id: str
    scope: str
    path: Path | None
    origin: str | None
    requires: tuple[str, ...]
    content: dict | None = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate catalog key: {key}")
        result[key] = value
    return result


def absolute_path(value, home):
    require(isinstance(value, str) and bool(value), "Expected an absolute path or ~/ path.")
    path = home / value[2:] if value.startswith("~/") else Path(value)
    require(path.is_absolute(), "Relative catalog paths are not supported.")
    return path.resolve()


def parse_catalog(data, home):
    require(
        isinstance(data, dict) and set(data) == {"schemaVersion", "layers"}
        and type(data["schemaVersion"]) is int and data["schemaVersion"] in (1, 2),
        "Unsupported capability catalog format.",
    )
    require(isinstance(data["layers"], list) and data["layers"], "Expected a nonempty layer list.")
    layers, seen = [], set()
    for item in data["layers"]:
        fields = {"id", "scope", "requires"}
        if data["schemaVersion"] == 2:
            fields.add("content")
        require(isinstance(item, dict) and set(item) == fields, "Invalid layer fields.")
        content = item.get("content")
        if data["schemaVersion"] == 2:
            require(isinstance(content, dict), "Expected layer content configuration.")
        name = item["id"]
        require(isinstance(name, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), "Invalid layer ID.")
        require(name not in seen, "Duplicate layer ID.")
        dependencies = item["requires"]
        require(
            isinstance(dependencies, list) and all(isinstance(value, str) for value in dependencies)
            and len(set(dependencies)) == len(dependencies)
            and all(value in seen for value in dependencies),
            "Layer dependencies must be unique and declared earlier.",
        )
        scope = item["scope"]
        require(isinstance(scope, dict), "Invalid layer scope.")
        kind = scope.get("type")
        fields = {
            "always": {"type"},
            "directory": {"type", "path"},
            "repository": {"type", "path", "origin"},
        }
        require(isinstance(kind, str) and kind in fields and set(scope) == fields[kind], "Unsupported layer scope.")
        path = None if kind == "always" else absolute_path(scope["path"], home)
        origin = scope.get("origin")
        if kind == "repository":
            require(
                isinstance(origin, str) and bool(origin.strip()) and not origin.startswith("-")
                and not any(ord(char) < 32 for char in origin),
                "Invalid repository origin.",
            )
            parsed = urlsplit(origin)
            require(
                parsed.password is None
                and not (parsed.scheme in ("http", "https") and parsed.username is not None)
                and not parsed.query and not parsed.fragment,
                "Do not put repository credentials or URL parameters in the catalog.",
            )
        layers.append(Layer(name, kind, path, origin, tuple(dependencies), content))
        seen.add(name)
    return tuple(layers)


def load_catalog(path=DEFAULT_CATALOG):
    try:
        data = json.loads(Path(path).expanduser().read_text(), object_pairs_hook=unique_object)
    except FileNotFoundError as error:
        raise ValueError(f"Capability catalog missing: {path}. No environment changed.") from error
    return parse_catalog(data, Path.home())


def repository_identity(workspace):
    # Metadata only. Ignore inherited Git overrides; do not fetch or run hooks.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    def git(*args):
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
             "-C", str(workspace), *args],
            env=env, capture_output=True, text=True, timeout=30,
        )
        require(result.returncode == 0, "Could not verify repository identity. No environment changed.")
        return result.stdout.strip()
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    origin = git("config", "--local", "--get", "remote.origin.url")
    return root, origin


def select_layers(workspace, layers, identity=repository_identity):
    workspace = Path(workspace).expanduser().resolve()
    require(workspace.is_dir(), "Workspace must be an existing directory.")
    selected = []
    for layer in layers:
        if layer.scope != "always" and not workspace.is_relative_to(layer.path):
            continue
        if layer.scope == "repository":
            root, origin = identity(workspace)
            require(
                root == layer.path and origin == layer.origin,
                f"Repository identity mismatch for layer {layer.id}. No environment changed.",
            )
        require(
            set(layer.requires).issubset(item.id for item in selected),
            f"Missing required layers for {layer.id}. No environment changed.",
        )
        selected.append(layer)
    return tuple(selected)


def show_plan(workspace, catalog=DEFAULT_CATALOG):
    workspace = Path(workspace).expanduser().resolve()
    selected = select_layers(workspace, load_catalog(catalog))
    print(f"Prosjekt: {workspace}")
    print("Forventede innholdslag:")
    for layer in selected:
        print(f"  {layer.id} ({layer.scope})")
    if not selected:
        print("  Ingen lag matcher.")
    print(
        "Bare lagvalg er kontrollert. Kommandoen installerer eller verifiserer ikke "
        "skills, MCP, agenter eller hovedinstruksjoner."
    )
    return selected
