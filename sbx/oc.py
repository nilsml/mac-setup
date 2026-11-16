#!/usr/bin/env python3
"""Velg, åpne og stopp OpenCode-sandboxer. Ingen sletting eller oppgradering."""

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import start


ROOT = Path(__file__).resolve().parent


def sandboxes():
    result = subprocess.run(
        ["sbx", "ls", "--format", "json"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    entries = json.loads(result.stdout)
    if not isinstance(entries, list):
        raise ValueError("Ukjent svar fra sbx ls. Ingen handling utført.")
    selected = [entry for entry in entries if entry.get("agent") == "opencode"]
    for entry in selected:
        validate_name(entry.get("name", ""))
    return sorted(selected, key=lambda entry: entry["name"].casefold())


def validate_name(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,61}[A-Za-z0-9]", name) or name == "default":
        raise ValueError("Ugyldig sandboxnavn.")


def workspace_label(entry):
    return ", ".join(entry.get("workspaces", [])) or "(uten prosjektmount)"


def show(entries):
    for index, entry in enumerate(entries, 1):
        print(f"{index:>2}. {entry['name']} [{entry.get('status', 'ukjent')}]")
        print(f"    {workspace_label(entry)}")
    if not entries:
        print("Ingen OpenCode-sandboxer. Opprett med: oc .")


def choose(entries):
    if not entries:
        raise ValueError("Ingen miljøer å velge mellom. Opprett med: oc .")
    show(entries)
    if not sys.stdin.isatty():
        raise ValueError("Velg navn eksplisitt utenfor terminalen: oc open NAVN / oc shell NAVN / oc stop NAVN.")
    answer = input("Velg nummer, eller q for å avbryte: ").strip()
    if answer.lower() == "q":
        return None
    if not answer.isdecimal() or not 1 <= int(answer) <= len(entries):
        raise ValueError("Ugyldig valg. Ingen handling utført.")
    return entries[int(answer) - 1]


def named(entries, name):
    validate_name(name)
    matches = [entry for entry in entries if entry["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Fant ikke en eksisterende OpenCode-sandbox med navn {name}.")
    return matches[0]


def project_matches(entries, workspace):
    return [
        entry for entry in entries
        if entry.get("workspaces")
        and Path(entry["workspaces"][0]).resolve() == workspace
    ]


def checked_info(entry):
    info = start.inspect_sandbox(entry["name"])
    if info.get("name") != entry["name"] or info.get("agent") != "opencode":
        raise ValueError("Sandboxen har endret seg siden oversikten ble lest. Avbryter.")
    return info


def execute(command, dry_run):
    print(shlex.join(command), flush=True)
    if not dry_run:
        subprocess.run(command, check=True)


def open_existing(entry, dry_run=False, all_tabs=False):
    info = checked_info(entry)
    command = ["sbx", "run", "--name", entry["name"]]
    if info.get("workspace"):
        command += ["--workdir", info["workspace"]]
    if all_tabs:
        command += ["--env", 'OPENCODE_CLI_CONFIG_CONTENT={"tabs":{"mode":"on","scope":"global"}}']
    execute(command, dry_run)


def shell_existing(entry, dry_run=False):
    info = checked_info(entry)
    command = ["sbx", "exec", "-it", "-u", "agent"]
    if info.get("workspace"):
        command += ["--workdir", info["workspace"]]
    command += [entry["name"], "zsh", "-l"]
    execute(command, dry_run)


def stop_existing(entry, dry_run=False):
    info = checked_info(entry)
    if info.get("state") == "stopped":
        print(f"{entry['name']} er allerede stoppet.")
        return
    if info.get("state") != "running":
        raise ValueError("Sandboxen er i en uventet tilstand. Kontroller med sbx inspect før stopp.")
    if not dry_run:
        if not sys.stdin.isatty():
            raise ValueError("Stopp krever bekreftelse i terminalen. Bruk sbx stop NAVN for eksplisitt automatisering.")
        print(f"Stopp {entry['name']}? Aktive prosesser avbrytes. Data beholdes.")
        if input("Bekreft [j/N]: ").strip().lower() not in ("j", "ja", "y", "yes"):
            print("Avbrutt.")
            return
    execute(["sbx", "stop", entry["name"]], dry_run)


def project(entries, path, args):
    workspace = Path(path).expanduser().resolve()
    if not workspace.is_dir() or workspace in (Path("/"), Path.home()):
        raise ValueError("Velg en eksisterende prosjektmappe, ikke hjemmemappen eller filsystemroten.")
    matches = project_matches(entries, workspace)
    name = args.name
    if not name and matches:
        selected = matches[0] if len(matches) == 1 else choose(matches)
        if selected is None:
            return
        name = selected["name"]
    command = [sys.executable, str(ROOT / "start.py"), str(workspace)]
    if name:
        validate_name(name)
        command += ["--name", name]
    if args.dry_run:
        command.append("--dry-run")
    if args.all_tabs:
        command.append("--all-tabs")
    if args.setup_only:
        command.append("--setup-only")
    # start.py eier opprettelse, mountkontroll, secrets og første bekreftelse.
    # Kjør også i dry-run for å vise den eksisterende lesende oppstartsplanen.
    subprocess.run(command, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Uten argument: meny. Eksempler: oc . | oc list | oc open NAVN | oc shell NAVN | oc stop NAVN",
    )
    parser.add_argument("action", nargs="?", default="menu", help="list, open, shell, stop, project eller prosjektsti")
    parser.add_argument("target", nargs="?", help="Sandboxnavn, eller sti etter project")
    parser.add_argument("--name", help="Eksplisitt sandboxnavn ved prosjektoppstart")
    parser.add_argument("--dry-run", action="store_true", help="Vis plan uten å starte eller endre miljøer")
    parser.add_argument("--all-tabs", action="store_true", help="Vis tabs fra samme OpenCode-server")
    parser.add_argument("--setup-only", action="store_true", help="Bare prosjektoppsett, uten TUI")
    args = parser.parse_args(argv)
    is_project = args.action not in ("menu", "list", "open", "shell", "stop")
    if not is_project and (args.name or args.setup_only):
        parser.error("--name og --setup-only gjelder bare prosjektoppstart.")
    if args.all_tabs and args.action in ("list", "shell", "stop"):
        parser.error("--all-tabs gjelder bare åpning av OpenCode.")
    if args.action in ("menu", "list") and args.target:
        parser.error("Denne kommandoen tar ikke et ekstra argument.")
    if is_project and args.action != "project" and args.target:
        parser.error("Bruk oc project STI for eksplisitt prosjektoppstart.")
    entries = sandboxes()
    if is_project:
        project(entries, (args.target or ".") if args.action == "project" else args.action, args)
    elif args.action == "list":
        show(entries)
    else:
        entry = named(entries, args.target) if args.target else choose(entries)
        if entry is None:
            return
        action = args.action
        if action == "menu":
            answer = input("Enter: åpne OpenCode | t: terminal | s: stopp | q: avbryt: ").strip().lower()
            if answer == "q":
                return
            if answer not in ("", "t", "s"):
                raise ValueError("Ugyldig handling. Ingen handling utført.")
            action = {"": "open", "t": "shell", "s": "stop"}[answer]
        if action == "stop":
            stop_existing(entry, args.dry_run)
        elif action == "shell":
            shell_existing(entry, args.dry_run)
        else:
            open_existing(entry, args.dry_run, args.all_tabs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAvbrutt.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"Feil: {error}", file=sys.stderr)
        sys.exit(1)
