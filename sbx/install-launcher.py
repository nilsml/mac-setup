#!/usr/bin/env python3
"""Plan or install the small, standalone sbx launcher."""

import argparse
import os
from pathlib import Path
import shutil


SOURCE = Path(__file__).resolve().parent
REPOSITORY = SOURCE.parent
DEFAULT_DESTINATION = Path.home() / ".local/share/opencode-sbx/launcher"
FILES = (
    "oc.py", "start.py", "profiles.py", "content.py", "content_runtime.py",
    "scripts/register-model-secrets.py",
    "mcp.py", "mcp_host.py",
    "logseq.py", "mcp_runtime.py",
    "personal/.dockerignore", "personal/install.sh", "personal/personal.dockerfile",
    "personal/personal.yaml", "personal/files/preferences.md",
    "personal/files/powerline/tui.tsx", "personal/files/zshrc",
    "personal/files/cli.json", "personal/files/aliases.zsh",
    "models/.dockerignore", "models/install.py", "models/models.dockerfile",
    "models/models.yaml", "models/providers.json",
)
KITS = ("personal", "models")


def source_files():
    """Return a sorted, fully checked list of relative source paths."""
    selected = []

    def check(path):
        if path.is_symlink():
            raise ValueError(f"Symbolic link in source: {path}")

    for name in FILES:
        path = SOURCE / name
        # Check parents too, including scripts/, before following them.
        for parent in reversed(path.relative_to(SOURCE).parents):
            check(SOURCE / parent)
        check(path)
        if not path.is_file():
            raise ValueError(f"Missing source file: {path}")
        selected.append(Path(name))

    return sorted(selected)


def install(destination, apply=False):
    """Return the copy plan; write it only when apply is true."""
    destination = Path(os.path.abspath(os.path.expanduser(destination)))
    if destination.is_symlink():
        raise ValueError(f"Destination is a symbolic link: {destination}")
    resolved = destination.resolve()
    repository = REPOSITORY.resolve()
    if (resolved == Path(resolved.anchor) or resolved == Path.home().resolve()
            or resolved.is_relative_to(repository)):
        raise ValueError(f"Unsafe destination: {destination}")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f"Destination is not an empty directory: {destination}")
    files = source_files()
    if apply:
        destination.mkdir(parents=True, exist_ok=True)
        for relative in files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / relative, target)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", default=DEFAULT_DESTINATION, type=Path)
    parser.add_argument("--apply", action="store_true", help="copy files instead of only listing them")
    args = parser.parse_args()
    try:
        files = install(args.destination, apply=args.apply)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"{'Installed' if args.apply else 'Would install'} to {args.destination}:")
    for path in files:
        print(f"  {path}")


if __name__ == "__main__":
    main()
