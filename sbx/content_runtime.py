"""Register read-only mounted OpenCode content inside a disposable sandbox."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path):
    try:
        return json.loads(path.read_text(), object_pairs_hook=_json_object)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read valid JSON from {path}: {error}") from error


FIELDS = {"skills", "instructions", "agents", "default_agent"}


def _roots(payload, mount_root):
    """Return content roots: read-only mounts, plus the project when it is a source."""
    _require(isinstance(payload, dict) and set(payload) in (FIELDS, FIELDS | {"workspace"}),
             "Invalid content payload fields.")
    roots = []
    if "workspace" in payload:
        workspace = payload["workspace"]
        _require(isinstance(workspace, str) and workspace.startswith("/")
                 and workspace not in ("/", str(Path.home())),
                 "Invalid workspace content root.")
        roots.append(Path(workspace).resolve(strict=True))
        _require(str(roots[0]) == workspace and roots[0].is_dir(),
                 "Workspace content root must be an existing, unaliased directory.")
        if Path(mount_root).is_dir():
            roots.append(Path(mount_root).resolve(strict=True))
    else:
        roots.append(Path(mount_root).resolve(strict=True))
        _require(roots[0].is_dir(), "Mount root must be a directory.")
    return tuple(roots)


def _boundary(path, roots):
    for root in roots:
        if str(path).startswith(str(root) + "/"):
            return root
    raise ValueError(f"Content path must be under {', '.join(map(str, roots))}: {path!r}")


def _validate(payload, mount_root):
    roots = _roots(payload, mount_root)

    def mounted(value, kind):
        _require(isinstance(value, str), f"Invalid content path: {value!r}")
        root = _boundary(value, roots)
        path = Path(value)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"Missing content path: {value}") from error
        _require(resolved.is_relative_to(root) and getattr(resolved, kind)(),
                 f"Invalid mounted content path: {value}")
        return value

    skills, instructions = payload["skills"], payload["instructions"]
    _require(isinstance(skills, list) and all(isinstance(x, str) for x in skills),
             "skills must be a list of paths.")
    _require(isinstance(instructions, list) and all(isinstance(x, str) for x in instructions),
             "instructions must be a list of paths.")
    _require(len(set(skills)) == len(skills) and len(set(instructions)) == len(instructions),
             "Duplicate content path.")
    skills = [mounted(path, "is_dir") for path in skills]
    instructions = [mounted(path, "is_file") for path in instructions]
    agents = payload["agents"]
    default = payload["default_agent"]
    if agents is not None:
        agents = mounted(agents, "is_dir")
    else:
        _require(default is None, "default_agent requires an agents directory.")
    if default is not None:
        _require(isinstance(default, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", default),
                 "Invalid default_agent.")
        default_path = Path(agents) / (default + ".md")
        _require(default_path.is_file()
                 and default_path.resolve().is_relative_to(_boundary(agents, roots)),
                 "default_agent Markdown file is missing.")
    return {"skills": skills, "instructions": instructions,
            "agents": agents, "default_agent": default}


def _skill_ids(directory, boundary, depth=0):
    """Yield discoverable IDs conservatively without following external links."""
    resolved = directory.resolve(strict=True)
    _require(resolved.is_relative_to(boundary), f"Skill path escapes content root: {directory}")
    marker = directory / "SKILL.md"
    if marker.exists() or marker.is_symlink():
        _require(marker.resolve(strict=True).is_relative_to(boundary),
                 f"Skill file escapes content root: {marker}")
        if marker.is_file():
            yield directory.name
            return
    for entry in directory.iterdir():
        if entry.name.startswith(".") or entry.name in ("SKILL.md", "node_modules"):
            continue
        if entry.is_symlink():
            try:
                target = entry.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError(f"Broken skill symlink: {entry}") from error
            _require(target.is_relative_to(boundary),
                     f"Skill path escapes source: {entry}")
        if depth == 0 and entry.suffix == ".md" and (entry.is_file() or entry.is_symlink()):
            if entry.is_file():
                yield entry.stem
        elif depth < 6 and entry.is_dir():
            yield from _skill_ids(entry, boundary, depth + 1)


def _check_collisions(config, payload, home, roots):
    expected = set(payload["skills"])
    existing = config.get("skills", [])
    _require(isinstance(existing, list), "Expected skills as a list.")
    _require(all(isinstance(item, str) for item in existing), "Invalid skills entry.")
    _require(set(existing) <= expected, "Existing unrelated skills entries cannot be verified.")
    proposed = set()
    for path in payload["skills"]:
        for skill_id in _skill_ids(Path(path), _boundary(path, roots)):
            _require(skill_id not in proposed, f"Duplicate skill ID: {skill_id}")
            proposed.add(skill_id)
    # Tools such as twg link global skills to their own folder under home.
    home_boundary = home.resolve()
    for path in (home / ".config/opencode/skills",):
        if path.is_symlink():
            raise ValueError(f"Cannot verify symlinked global skills directory: {path}")
        if path.is_dir():
            for skill_id in _skill_ids(path, home_boundary):
                _require(skill_id not in proposed, f"Skill ID conflicts with existing global skill: {skill_id}")
    for path in (home / ".agents/skills", home / ".claude/skills"):
        if path.is_symlink():
            raise ValueError(f"Cannot verify symlinked compatibility skills directory: {path}")
        if path.is_dir():
            for skill_id in _skill_ids(path, home_boundary):
                _require(skill_id not in proposed, f"Skill ID conflicts with existing global skill: {skill_id}")
    configured_agents = config.get("agents", {})
    _require(isinstance(configured_agents, dict), "Expected agents as an object.")
    _require("agent" not in config,
             "Legacy 'agent' config requires manual legacy-config-review.")
    if payload["agents"] is not None:
        boundary = _boundary(payload["agents"], roots)
        for agent_id in _agent_ids(Path(payload["agents"]), boundary):
            _require(agent_id not in configured_agents,
                     f"Agent ID conflicts with configured agent: {agent_id}")


def _agent_ids(directory, boundary, ancestors=frozenset(), prefix=()):
    """Return path-based agent IDs while validating every visible symlink."""
    try:
        resolved = directory.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Invalid agent directory: {directory}") from error
    _require(resolved.is_relative_to(boundary),
             f"Agent path escapes content root: {directory}")
    _require(resolved not in ancestors, f"Agent directory symlink cycle: {directory}")
    ancestors = ancestors | {resolved}
    found = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        if entry.name.startswith(".") or entry.name == "node_modules":
            continue
        if entry.is_symlink():
            try:
                target = entry.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError(f"Broken agent symlink: {entry}") from error
            _require(target.is_relative_to(boundary),
                     f"Agent path escapes content root: {entry}")
        if entry.is_dir():
            found.extend(_agent_ids(entry, boundary, ancestors, (*prefix, entry.name)))
        elif entry.suffix == ".md" and entry.is_file():
            try:
                target = entry.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError(f"Invalid agent file: {entry}") from error
            _require(target.is_relative_to(boundary),
                     f"Agent file escapes content root: {entry}")
            found.append("/".join((*prefix, entry.stem)))
    return found


def _load_config(home):
    root = home / ".config/opencode"
    config_path = root / "opencode.json"
    _require(not root.is_symlink() and not (home / ".config").is_symlink(),
             "Refusing symlinked OpenCode config path.")
    _require(not (root / "opencode.jsonc").exists() and not (root / "opencode.jsonc").is_symlink(),
             "Competing opencode.jsonc exists.")
    _require(not config_path.is_symlink(), "Refusing symlinked opencode.json.")
    config = _read(config_path) if config_path.exists() else {}
    _require(isinstance(config, dict), "opencode.json must contain an object.")
    return root, config_path, config


def _atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix=".opencode-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _expected_config(config, payload):
    updated = dict(config)
    updated.setdefault("$schema", "https://opencode.ai/config.json")
    for key in ("skills", "instructions"):
        current = updated.get(key, [])
        _require(isinstance(current, list) and all(isinstance(x, str) for x in current),
                 f"Expected {key} as a list of paths.")
        for path in payload[key]:
            if path not in current:
                current = [*current, path]
        updated[key] = current
    default = payload["default_agent"]
    if default is not None:
        current = updated.get("default_agent")
        _require(current is None or current == default,
                 f"Conflicting default_agent: {current!r}")
        if current is None:
            updated["default_agent"] = default
    return updated


def _marker(home):
    return home / ".local/state/opencode-sbx/content.json"


def check(home: Path, payload, mount_root=Path("/opt/opencode-content")):
    home = Path(home)
    expected = _validate(payload, mount_root)
    _, config_path, config = _load_config(home)
    _check_collisions(config, expected, home, _roots(payload, mount_root))
    configured = _expected_config(config, expected)
    _require(configured == config, "OpenCode content configuration has drifted.")
    link = home / ".config/opencode/agents"
    if expected["agents"] is None:
        _require(not link.is_symlink(), "Unexpected agents symlink.")
    else:
        _require(link.is_symlink() and str(link.resolve()) == str(Path(expected["agents"]).resolve()),
                 "Agents symlink is missing or differs.")
    marker = _marker(home)
    _require(not marker.is_symlink() and marker.is_file(), "Content setup marker is missing.")
    _require(_read(marker) == expected, "Content setup marker differs from requested payload.")
    return True


def configure(home: Path, payload, mount_root=Path("/opt/opencode-content")):
    home = Path(home)
    expected = _validate(payload, mount_root)
    root, config_path, config = _load_config(home)
    _check_collisions(config, expected, home, _roots(payload, mount_root))
    updated = _expected_config(config, expected)
    link = root / "agents"
    if expected["agents"] is None:
        _require(not link.exists() and not link.is_symlink(),
                 "Existing agents path is manually managed; refusing to replace.")
    elif link.is_symlink():
        _require(str(link.resolve()) == str(Path(expected["agents"]).resolve()),
                 "Existing agents symlink differs; refusing to replace.")
    else:
        _require(not link.exists(), "Existing agents path is manually managed; refusing to replace.")

    marker = _marker(home)
    _require(not marker.is_symlink(), "Refusing symlinked content marker.")
    _require(not marker.is_dir(), "Content marker path is a directory.")
    config_changed = updated != config or not config_path.exists()
    marker_changed = not marker.is_file() or _read(marker) != expected
    created_link = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        if expected["agents"] is not None and not link.is_symlink():
            link.symlink_to(expected["agents"])
            created_link = True
        if config_changed:
            _atomic_json(config_path, updated)
        if marker_changed:
            marker.parent.mkdir(parents=True, exist_ok=True)
            _atomic_json(marker, expected)
    except Exception:
        if created_link:
            link.unlink(missing_ok=True)
        raise
    return True


if __name__ == "__main__":
    payload = json.load(sys.stdin, object_pairs_hook=_json_object)
    if sys.argv[1:] == ["--check"]:
        check(Path.home(), payload)
    elif not sys.argv[1:]:
        configure(Path.home(), payload)
    else:
        raise SystemExit("Usage: content_runtime.py [--check]")
