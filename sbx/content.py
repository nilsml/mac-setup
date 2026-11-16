"""Read-only planning for live content mounts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re


@dataclass(frozen=True)
class Mount:
    host: Path
    target: str


@dataclass(frozen=True)
class ContentPlan:
    mounts: tuple[Mount, ...]
    skills: tuple[str, ...]
    instructions: tuple[str, ...]
    agents: str | None
    default_agent: str | None


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _safe_host(path):
    _require(not any(c == ":" or ord(c) < 32 or ord(c) == 127 for c in str(path)),
             f"Unsafe host path: {path!s}")


def _relative(value):
    _require(isinstance(value, str) and bool(value), "Expected a nonempty relative path.")
    _safe_host(value)
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(part not in ("", ".", "..") for part in value.split("/"))
             and "\\" not in value, f"Unsafe relative path: {value}")
    return path


def _inside(path, root):
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            _require(not candidate.readlink().is_absolute(),
                     f"Absolute symlink cannot be remapped into the sandbox: {candidate}")
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Cannot resolve path: {path}") from error
    _safe_host(resolved)
    _require(resolved.is_relative_to(root), f"Path escapes source: {path}")
    _require(resolved.exists(), f"Missing or broken content path: {path}")
    return resolved


def _skill_ids(root, boundary):
    """Mirror documented path-based discovery, without following escaping links."""
    def visit(directory, depth, ancestors):
        resolved = _inside(directory, boundary)
        _require(resolved not in ancestors, f"Directory symlink cycle: {directory}")
        ancestors = ancestors | {resolved}
        entries = sorted(directory.iterdir(), key=lambda item: item.name)
        marker = directory / "SKILL.md"
        if marker.exists() or marker.is_symlink():
            _inside(marker, boundary)
            if marker.is_file():
                yield directory.name
                return
        for entry in entries:
            if entry.name.startswith(".") or entry.name == "node_modules" or entry.name == "SKILL.md":
                continue
            if depth == 0 and entry.name.endswith(".md"):
                _inside(entry, boundary)
                if entry.is_file():
                    yield entry.stem
            elif depth < 6:
                if entry.is_symlink():
                    _inside(entry, boundary)
                if entry.is_dir():
                    yield from visit(entry, depth + 1, ancestors)
    yield from visit(root, 0, set())


def _agent_ids(root, boundary):
    # Agent IDs retain grouping directories relative to the agents root.
    def visit(directory, ancestors):
        resolved = _inside(directory, boundary)
        _require(resolved not in ancestors, f"Directory symlink cycle: {directory}")
        ancestors = ancestors | {resolved}
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            if entry.name.startswith(".") or entry.name == "node_modules":
                continue
            if entry.is_symlink():
                _inside(entry, boundary)
            if entry.is_dir():
                yield from visit(entry, ancestors)
            elif entry.name.endswith(".md") and entry.is_file():
                _inside(entry, boundary)
                yield entry.relative_to(root).with_suffix("").as_posix()
    yield from visit(root, set())


def build_plan(workspace, selected, directory=None):
    """Validate selected (layer ID, spec) pairs and return an immutable mount plan."""
    workspace = Path(workspace).expanduser().resolve()
    _safe_host(workspace)
    _require(workspace.is_dir(), "Workspace must be an existing directory.")
    directory = workspace if directory is None else Path(directory).expanduser().resolve()
    _safe_host(directory)
    _require(directory.is_dir() and directory.is_relative_to(workspace),
             "Directory must be an existing directory inside workspace.")
    levels = [workspace]
    for part in directory.relative_to(workspace).parts:
        levels.append(levels[-1] / part)

    mounts, skills, instructions = [], [], []
    ids, sources, skill_ids, instruction_paths = set(), set(), set(), set()
    agents = default_agent = None
    supplied_agent_ids = set()
    for item in selected:
        _require(isinstance(item, (tuple, list)) and len(item) == 2, "Invalid selected layer.")
        layer, spec = item
        _require(isinstance(layer, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", layer),
                 "Invalid layer ID.")
        _require(layer not in ids, f"Duplicate layer ID: {layer}")
        ids.add(layer)
        _require(isinstance(spec, dict) and {"source", "skills"} <= spec.keys()
                 and spec.keys() <= {"source", "skills", "instructions", "agents", "defaultAgent"},
                 f"Invalid fields for layer {layer}.")
        source_value = spec["source"]
        _require(isinstance(source_value, str) and bool(source_value), "Invalid source path.")
        _safe_host(source_value)
        _require(source_value.startswith("/") or source_value.startswith("~/"),
                 "Source must be absolute or start with ~/")
        source = Path(source_value).expanduser().resolve()
        _safe_host(source)
        _require(source != Path("/") and source != Path.home().resolve() and source.is_dir(),
                 "Source must be an existing directory other than root or home.")
        _require(source not in sources, f"Duplicate source: {source}")
        sources.add(source)
        target = f"/opt/opencode-content/{layer}"
        container_path = Path(target)
        _require(
            not workspace.is_relative_to(container_path) and not container_path.is_relative_to(workspace),
            "Content target overlaps the project mount.",
        )
        mounts.append(Mount(source, target))
        for key in ("skills", "instructions"):
            values = spec.get(key, [])
            _require(isinstance(values, list) and (key != "skills" or bool(values)),
                     f"{key} must be a {'nonempty ' if key == 'skills' else ''}list.")
            for value in values:
                rel = _relative(value)
                path = source.joinpath(*rel.parts)
                _inside(path, source)
                _require(path.is_dir() if key == "skills" else path.is_file(),
                         f"Missing {key} path: {path}")
                result = f"{target}/{rel.as_posix()}"
                if key == "skills":
                    _require(result not in skills, f"Duplicate skills path: {result}")
                    skills.append(result)
                    for skill in _skill_ids(path, source):
                        _require(skill not in skill_ids, f"Duplicate skill ID: {skill}")
                        skill_ids.add(skill)
                else:
                    resolved = _inside(path, source)
                    _require(resolved not in instruction_paths, f"Duplicate instruction path: {path}")
                    instruction_paths.add(resolved)
                    instructions.append(result)
        if "agents" in spec:
            _require(agents is None, "Only one agent source is supported.")
            rel = _relative(spec["agents"])
            path = source.joinpath(*rel.parts)
            _inside(path, source)
            _require(path.is_dir(), f"Missing agents directory: {path}")
            agents = f"{target}/{rel.as_posix()}"
            for agent in _agent_ids(path, source):
                _require(agent not in supplied_agent_ids, f"Duplicate agent ID: {agent}")
                supplied_agent_ids.add(agent)
        if "defaultAgent" in spec:
            default_agent = spec["defaultAgent"]
            _require(isinstance(default_agent, str)
                     and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", default_agent),
                     "Invalid default agent ID.")
            _require("agents" in spec and default_agent in supplied_agent_ids,
                     "Default agent requires a corresponding agent Markdown file.")

    for level in levels:
        for folder in (".opencode/skills", ".agents/skills", ".claude/skills"):
            path = level / folder
            if path.is_dir():
                for skill in _skill_ids(path, workspace):
                    _require(skill not in skill_ids, f"Duplicate skill ID: {skill}")
                    skill_ids.add(skill)
        path = level / ".opencode/agents"
        if supplied_agent_ids and path.is_dir():
            for agent in _agent_ids(path, workspace):
                _require(agent not in supplied_agent_ids, f"Duplicate agent ID: {agent}")
    return ContentPlan(tuple(mounts), tuple(skills), tuple(instructions), agents, default_agent)
