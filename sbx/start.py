#!/usr/bin/env python3
"""Opprett eller gjenåpne et eksplisitt valgt OpenCode-arbeidsområde."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def sandbox_name(workspace):
    slug = re.sub(r"[^a-z0-9]+", "-", workspace.name.lower()).strip("-") or "workspace"
    digest = hashlib.sha256(str(workspace).encode()).hexdigest()[:10]
    return f"oc-{slug[:35]}-{digest}"


def inspect_commands(workspace, name, directory, all_tabs):
    create = [
        "sbx", "create", "opencode", str(workspace), "--name", name,
        "--kit", str(ROOT / "personal"), "--kit", str(ROOT / "models"),
        "--skills", "off", "--static-mcp", "none",
    ]
    attach = ["sbx", "run", "--name", name, "--workdir", str(directory)]
    if all_tabs:
        attach += [
            "--env",
            'OPENCODE_CLI_CONFIG_CONTENT={"tabs":{"mode":"on","scope":"global"}}',
        ]
    return create, attach


def validate_existing(info, workspace):
    if info.get("agent") != "opencode":
        raise ValueError("Navnet tilhører en annen agent. Velg et annet --name.")
    mounted = info.get("workspace")
    if not mounted or Path(mounted).resolve() != workspace:
        raise ValueError("Sandboxen tilhører en annen arbeidsmappe. Velg et annet --name.")
    mounts = info.get("host_mounts", [])
    if (
        len(mounts) != 1
        or Path(mounts[0].get("host_path", "")).resolve() != workspace
        or mounts[0].get("container_target") != str(workspace)
        or mounts[0].get("read_only") is not False
    ):
        raise ValueError("Sandboxens vertsmounts avviker fra én skrivbar prosjektmappe.")
    expected = {str(ROOT / "personal"), str(ROOT / "models")}
    installed = {
        str(Path(kit).resolve())
        for kit in info.get("kits", [])
        if isinstance(kit, str) and kit.startswith("/")
    }
    if not expected.issubset(installed):
        raise ValueError("Sandboxen mangler våre mixiner. Velg et nytt --name.")


def inspect_sandbox(name):
    result = subprocess.run(
        ["sbx", "inspect", name, "--format", "json"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def missing_secrets(info):
    stored = {entry["name"] for entry in info.get("secrets", [])}
    return [provider for provider in ("anthropic", "berget") if provider not in stored]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", default=".", help="Prosjektmappen; bare denne vertsmappen monteres")
    parser.add_argument("--name", help="Stabilt navn; ellers avledes navnet fra mappens absolutte sti")
    parser.add_argument("--workdir", help="Start i en undermappe i arbeidsområdet")
    parser.add_argument("--all-tabs", action="store_true", help="Vis tabs på tvers av mapper i samme OpenCode-server")
    parser.add_argument("--setup-only", action="store_true", help="Sett opp miljøet uten å åpne TUI")
    parser.add_argument("--dry-run", action="store_true", help="Vis plan uten å opprette, starte eller endre noe")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError("Arbeidsområdet må være en eksisterende mappe.")
    if workspace in (Path("/"), Path.home()):
        raise ValueError("Hele hjemmemappen og filsystemroten tillates ikke som arbeidsområde.")
    if ":" in str(workspace):
        raise ValueError("Kolon i arbeidssti støttes ikke, siden sbx bruker kolon i mount-syntaks.")
    directory = (workspace / Path(args.workdir or ".").expanduser()).resolve()
    if not directory.is_dir() or not directory.is_relative_to(workspace):
        raise ValueError("--workdir må være en eksisterende mappe i arbeidsområdet.")
    name = args.name or sandbox_name(workspace)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,61}[a-zA-Z0-9]", name) or name == "default":
        raise ValueError("Ugyldig sandboxnavn.")
    create, attach = inspect_commands(workspace, name, directory, args.all_tabs)

    # Oppslag er lesende. Ved feil avbrytes det, fremfor å anta at sandboxen mangler.
    names = subprocess.run(
        ["sbx", "ls", "-q"], check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    exists = name in names
    info = inspect_sandbox(name) if exists else {}
    if exists:
        validate_existing(info, workspace)
    print(f"Sandbox: {name}", flush=True)
    print(f"Skrivbart arbeidsområde: {workspace}", flush=True)
    if args.dry_run:
        if not exists:
            print(shlex.join(create))
        if missing_secrets(info):
            print("Registrer manglende Anthropic/Berget-nøkler fra Macens OpenCode.")
        if not args.setup_only:
            print(shlex.join(attach))
        return

    if not exists:
        if not sys.stdin.isatty():
            raise ValueError("Første oppsett må kjøres i en interaktiv terminal for godkjenning.")
        answer = input("Hele arbeidsområdet blir skrivbart fra sandboxen. Opprette? [y/N] ")
        if answer.strip().lower() not in ("y", "yes", "j", "ja"):
            raise ValueError("Avbrutt. Ingen sandbox opprettet.")
        subprocess.run(create, check=True)
        info = inspect_sandbox(name)
        validate_existing(info, workspace)

    missing = missing_secrets(info)
    if missing:
        command = [
            sys.executable, str(ROOT / "scripts/register-model-secrets.py"),
            "--sandbox", name, "--apply",
        ]
        for provider in missing:
            command += ["--provider", provider]
        subprocess.run(command, check=True)
    if not args.setup_only:
        subprocess.run(attach, check=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Feil: {error}", file=sys.stderr)
        sys.exit(1)
