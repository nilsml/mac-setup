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

import content
import logseq
import profiles


ROOT = Path(__file__).resolve().parent
LAUNCHERS = (Path.home() / ".local/share/opencode-sbx").resolve()


def sandbox_name(workspace):
    slug = re.sub(r"[^a-z0-9]+", "-", workspace.name.lower()).strip("-") or "workspace"
    digest = hashlib.sha256(str(workspace).encode()).hexdigest()[:10]
    return f"oc-{slug[:35]}-{digest}"


def inspect_commands(workspace, name, directory, all_tabs, plan=None):
    create = [
        "sbx", "create", "opencode", str(workspace),
    ]
    for mount in plan.mounts if plan else ():
        create.append(f"{mount.host}:{mount.target}:ro")
    create += [
        "--name", name,
        "--pull", "always",
        "--kit", str(ROOT / "personal"), "--kit", str(ROOT / "models"),
        "--skills", "off",
        # The upstream kit injects legacy {"permission":{"*":"allow"}}.
        # Its high-precedence wildcard overrides native global denials.
        # New sandboxes must use OpenCode's native configured permissions.
        "--env", "OPENCODE_CONFIG_CONTENT={}",
    ]
    attach = ["sbx", "run", "--name", name, "--workdir", str(directory)]
    if all_tabs:
        attach += [
            "--env",
            'OPENCODE_CLI_CONFIG_CONTENT={"tabs":{"mode":"on","scope":"global"}}',
        ]
    return create, attach


def sandbox_mounts(info):
    mounts = info.get("host_mounts", [])
    if not isinstance(mounts, list) or any(
        not isinstance(mount, dict)
        or not isinstance(mount.get("host_path"), str) or not mount["host_path"]
        or not isinstance(mount.get("container_target"), str) or not mount["container_target"]
        or type(mount.get("read_only")) is not bool
        for mount in mounts
    ):
        raise ValueError("Sandboxen har ugyldig mountmetadata.")
    return mounts


def validate_existing(info, workspace, plan=None, check_kits=True):
    if info.get("agent") != "opencode":
        raise ValueError("Navnet tilhører en annen agent. Velg et annet --name.")
    mounted = info.get("workspace")
    if not mounted or Path(mounted).resolve() != workspace:
        raise ValueError("Sandboxen tilhører en annen arbeidsmappe. Velg et annet --name.")
    mounts = sandbox_mounts(info)
    expected_mounts = {(workspace, str(workspace), False)}
    if plan:
        expected_mounts.update((mount.host, mount.target, True) for mount in plan.mounts)
    actual_mounts = []
    for mount in mounts:
        actual_mounts.append((
            Path(mount["host_path"]).resolve(), mount.get("container_target"), mount["read_only"],
        ))
    if len(actual_mounts) != len(expected_mounts) or set(actual_mounts) != expected_mounts:
        raise ValueError("Sandboxens vertsmounts avviker fra prosjektmappen og forventet skrivebeskyttet innhold.")
    if check_kits and not has_our_kits(info):
        raise ValueError("Sandboxen mangler våre mixiner. Velg et nytt --name.")


def has_our_kits(info):
    """Accept both mixins from this launcher or from one earlier installed launcher."""
    installed = {
        Path(kit).resolve()
        for kit in info.get("kits", [])
        if isinstance(kit, str) and kit.startswith("/")
    }
    roots = {kit.parent for kit in installed if kit.name == "personal"}
    roots &= {kit.parent for kit in installed if kit.name == "models"}
    return any(root == ROOT or root.parent == LAUNCHERS for root in roots)


def inspect_sandbox(name):
    result = subprocess.run(
        ["sbx", "inspect", name, "--format", "json"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def missing_secrets(info):
    stored = {entry["name"] for entry in info.get("secrets", [])}
    return [provider for provider in ("anthropic", "berget") if provider not in stored]


def content_payload(plan):
    payload = {
        "skills": list(plan.skills),
        "instructions": list(plan.instructions),
        "agents": plan.agents,
        "default_agent": plan.default_agent,
    }
    if plan.workspace_root:
        payload["workspace"] = plan.workspace_root
    return payload


def configure_content(name, plan, check=False):
    code = (ROOT / "content_runtime.py").read_text()
    command = ["sbx", "exec", "-u", "agent", name, "python3", "-c", code]
    if check:
        command.append("--check")
    subprocess.run(
        command, input=json.dumps(content_payload(plan)), text=True, check=True,
    )


def selected_content(workspace, directory, catalog):
    catalog = catalog.expanduser().resolve()
    if ROOT.is_relative_to(workspace) or catalog.is_relative_to(workspace):
        raise ValueError(
            "Launcher og aktiv katalog må ligge utenfor prosjektets skrivbare mount. "
            "Installer en gjennomgått launcher utenfor prosjektet først."
        )
    layers = profiles.select_layers(workspace, profiles.load_catalog(catalog))
    if not layers or any(layer.content is None for layer in layers):
        raise ValueError("Innholdsmounts krever katalogformat 2 med content for hvert valgt lag.")
    return content.build_plan(
        workspace, [(layer.id, layer.content) for layer in layers], directory=directory,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", default=".", help="Prosjektmappen som monteres skrivbart")
    parser.add_argument("--name", help="Stabilt navn; ellers avledes navnet fra mappens absolutte sti")
    parser.add_argument("--workdir", help="Start i en undermappe i arbeidsområdet")
    parser.add_argument("--all-tabs", action="store_true", help="Vis tabs på tvers av mapper i samme OpenCode-server")
    parser.add_argument("--setup-only", action="store_true", help="Sett opp miljøet uten å åpne TUI")
    parser.add_argument("--dry-run", action="store_true", help="Vis plan uten å opprette, starte eller endre noe")
    parser.add_argument("--content", action="store_true", help="Bruk levende skrivebeskyttede innholdslag ved nytt oppsett")
    parser.add_argument("--catalog", type=Path, help="Betrodd katalog for --content")
    args = parser.parse_args(argv)
    if args.catalog and not args.content:
        parser.error("--catalog krever --content.")
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
    # Oppslag er lesende. Ved feil avbrytes det, fremfor å anta at sandboxen mangler.
    names = subprocess.run(
        ["sbx", "ls", "-q"], check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    exists = name in names
    info = inspect_sandbox(name) if exists else {}
    has_content = any(
        str(mount.get("container_target", "")).startswith("/opt/opencode-content/")
        for mount in sandbox_mounts(info)
    )
    plan = None
    if args.content and exists and not has_content:
        # Content from the project itself needs no extra mount, so mounts alone
        # cannot distinguish it from an older environment without content.
        try:
            candidate = selected_content(workspace, directory, args.catalog or profiles.DEFAULT_CATALOG)
        except ValueError:
            candidate = None  # Older environments open unchanged, as before.
        if candidate and candidate.workspace_root and not candidate.mounts:
            plan, has_content = candidate, True
    legacy = args.content and exists and not has_content
    # Existing environments are never retrofitted. Secrets travel over stdin only.
    logseq_remote = logseq.connection(Path.home(), workspace) if not exists else None
    if args.content and (not exists or has_content) and plan is None:
        plan = selected_content(workspace, directory, args.catalog or profiles.DEFAULT_CATALOG)
    if has_content and not args.content:
        raise ValueError("Miljøet bruker innholdsmounts. Åpne med oc eller oppgi --content og samme katalog.")
    create, attach = inspect_commands(workspace, name, directory, args.all_tabs, plan)
    if exists:
        validate_existing(info, workspace, plan, check_kits=not legacy)
    print(f"Sandbox: {name}", flush=True)
    print(f"Skrivbart arbeidsområde: {workspace}", flush=True)
    if plan:
        for mount in plan.mounts:
            print(f"Skrivebeskyttet innhold: {mount.host} -> {mount.target}", flush=True)
        if plan.workspace_root:
            print(f"Innhold fra arbeidsområdet (skrivbart): {plan.workspace_root}", flush=True)
        print(f"Standardagent: {plan.default_agent or '(OpenCodes standard)'}", flush=True)
    elif args.content and exists:
        print("Eldre miljø åpnes uendret. Velg et nytt --name for innholdsmounts.", flush=True)
    if args.dry_run:
        if not exists:
            print(shlex.join(create))
        if not legacy and missing_secrets(info):
            print("Registrer manglende Anthropic/Berget-nøkler fra Macens OpenCode.")
        if plan:
            print("Kontroller innholdsoppsett." if exists else "Registrer skill-kilder, instruksjoner og globale agenter.")
        if logseq_remote:
            print("Registrer separat Logseq-forbindelse med innebygde agentrettigheter. Ingen tokenverdier vises.")
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
        validate_existing(info, workspace, plan)

    if plan:
        try:
            configure_content(name, plan, check=exists)
        except subprocess.CalledProcessError as error:
            raise ValueError(
                f"Innholdsoppsettet i {name} kunne ikke fullføres eller kontrolleres. "
                "Miljøet er beholdt uten automatisk reparasjon. Rett årsaken og velg et nytt "
                "--name for en ny sandbox. Bruk oc shell NAVN for diagnose."
            ) from error

    missing = [] if legacy else missing_secrets(info)
    if missing:
        command = [
            sys.executable, str(ROOT / "scripts/register-model-secrets.py"),
            "--sandbox", name, "--apply",
        ]
        for provider in missing:
            command += ["--provider", provider]
        subprocess.run(command, check=True)
    if logseq_remote:
        code = (ROOT / "mcp_runtime.py").read_text()
        try:
            subprocess.run(
                ["sbx", "exec", "-i", "-u", "agent", name, "python3", "-c", code],
                input=json.dumps(logseq_remote), text=True, check=True,
            )
        except subprocess.CalledProcessError as error:
            raise ValueError(
                "Separat Logseq-oppsett feilet. Miljøet er beholdt. "
                "Kontroller agentrettighetene før du oppretter et nytt miljø."
            ) from error
    if not args.setup_only:
        subprocess.run(attach, check=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Feil: {error}", file=sys.stderr)
        sys.exit(1)
