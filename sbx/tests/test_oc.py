import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
# Importer søskenmodulen på samme måte som når oc.py kjøres fra terminalen.
with patch.object(sys, "path", [str(ROOT), *sys.path]):
    spec = importlib.util.spec_from_file_location("oc_manager", ROOT / "oc.py")
    OC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(OC)

WORKSPACE = ROOT.parent
ENTRY = {"name": "opencode-work", "agent": "opencode", "status": "stopped", "workspaces": [str(WORKSPACE)]}
INFO = {"name": "opencode-work", "agent": "opencode", "state": "stopped", "workspace": str(WORKSPACE)}


def options(**changes):
    return argparse.Namespace(**{
        "name": None, "dry_run": False, "all_tabs": False, "setup_only": False, **changes,
    })


class ManagerTests(unittest.TestCase):
    def setUp(self):
        # Disse testene isolerer meny/delegering fra faktisk Git-oppdagelse.
        discovery = patch.object(OC, "project_workspace", side_effect=lambda directory: directory)
        discovery.start()
        self.addCleanup(discovery.stop)

    def test_listing_filters_other_agents_and_sorts(self):
        entries = [ENTRY, {**ENTRY, "name": "alpha"}, {"name": "other", "agent": "claude"}]
        with patch.object(OC.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(entries))) as run:
            self.assertEqual([e["name"] for e in OC.sandboxes()], ["alpha", "opencode-work"])
        self.assertEqual(run.call_args.args[0], ["sbx", "ls", "--format", "json"])

    def test_lookup_failure_does_not_fall_back_to_creation(self):
        with patch.object(OC.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["sbx"])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                OC.main(["."])
        self.assertEqual(run.call_count, 1)

    def test_unknown_name_does_not_create(self):
        with patch.object(OC, "sandboxes", return_value=[ENTRY]), patch.object(OC.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Fant ikke"):
                OC.main(["open", "missing"])
        run.assert_not_called()

    def test_project_reuses_legacy_name(self):
        with patch.object(OC.subprocess, "run") as run:
            OC.project([ENTRY], WORKSPACE, options())
        self.assertEqual(run.call_args.args[0][-2:], ["--name", "opencode-work"])

    def test_new_project_delegates_to_start(self):
        with patch.object(OC.subprocess, "run") as run:
            OC.project([], WORKSPACE, options())
        self.assertEqual(run.call_args.args[0], [sys.executable, str(ROOT / "start.py"), str(WORKSPACE), "--content"])

    def test_explicit_name_is_preserved(self):
        args = options()
        args.name = "another"
        with patch.object(OC.subprocess, "run") as run:
            OC.project([ENTRY], WORKSPACE, args)
        self.assertEqual(run.call_args.args[0][-2:], ["--name", "another"])

    def test_subdirectory_reuses_root_environment_and_preserves_workdir(self):
        directory = ROOT / "tests"
        with (
            patch.object(OC, "project_workspace", return_value=WORKSPACE),
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.project([ENTRY], directory, options())
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, str(ROOT / "start.py"), str(WORKSPACE), "--content",
             "--workdir", str(directory), "--name", "opencode-work"],
        )

    def test_legacy_subdirectory_mount_is_not_reused_or_migrated(self):
        directory = ROOT / "tests"
        entry = {**ENTRY, "workspaces": [str(directory)]}
        with (
            patch.object(OC, "project_workspace", return_value=WORKSPACE),
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.project([entry], directory, options())
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, str(ROOT / "start.py"), str(WORKSPACE), "--content", "--workdir", str(directory)],
        )

    def test_unsafe_detected_root_is_rejected(self):
        for root in (Path.home(), Path("/")):
            with (
                self.subTest(root=root),
                patch.object(OC, "project_workspace", return_value=root),
                patch.object(OC.subprocess, "run") as run,
                self.assertRaises(ValueError),
            ):
                OC.project([], WORKSPACE, options())
            run.assert_not_called()

    def test_subdirectory_with_multiple_root_matches_requires_choice(self):
        entries = [ENTRY, {**ENTRY, "name": "opencode-test"}]
        with (
            patch.object(OC, "project_workspace", return_value=WORKSPACE),
            patch.object(OC, "choose", return_value=entries[1]) as choose,
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.project(entries, ROOT / "tests", options(dry_run=True))
        choose.assert_called_once_with(entries)
        self.assertEqual(run.call_args.args[0][-3:], ["--name", "opencode-test", "--dry-run"])

    def test_ambiguous_project_requires_choice(self):
        entries = [ENTRY, {**ENTRY, "name": "opencode-test"}]
        with patch.object(OC.sys.stdin, "isatty", return_value=False), patch.object(OC.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Velg navn eksplisitt"):
                OC.project(entries, WORKSPACE, options())
        run.assert_not_called()

    def test_project_selection_can_be_cancelled(self):
        entries = [ENTRY, {**ENTRY, "name": "opencode-test"}]
        with patch.object(OC, "choose", return_value=None), patch.object(OC.subprocess, "run") as run:
            OC.project(entries, WORKSPACE, options())
        run.assert_not_called()

    def test_dry_run_project_delegates_read_only_plan(self):
        args = options()
        args.dry_run = args.setup_only = args.all_tabs = True
        with patch.object(OC.subprocess, "run") as run:
            OC.project([ENTRY], WORKSPACE, args)
        self.assertEqual(run.call_args.args[0][-3:], ["--dry-run", "--all-tabs", "--setup-only"])

    def test_open_uses_existing_name_and_workspace(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.open_existing(ENTRY)
        self.assertEqual(run.call_args.args[0], ["sbx", "run", "--name", "opencode-work", "--workdir", str(WORKSPACE)])

    def test_dry_run_open_does_not_start(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.open_existing(ENTRY, dry_run=True)
        run.assert_not_called()

    def test_shell_uses_agent_and_project_directory(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.shell_existing(ENTRY)
        self.assertEqual(
            run.call_args.args[0],
            ["sbx", "exec", "-it", "-u", "agent", "--workdir", str(WORKSPACE), "opencode-work", "zsh", "-l"],
        )

    def test_shell_without_workspace_uses_default_directory(self):
        with patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "workspace": None}), patch.object(OC.subprocess, "run") as run:
            OC.shell_existing(ENTRY)
        self.assertEqual(run.call_args.args[0], ["sbx", "exec", "-it", "-u", "agent", "opencode-work", "zsh", "-l"])

    def test_dry_run_shell_does_not_start(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.shell_existing(ENTRY, dry_run=True)
        run.assert_not_called()

    def test_shell_command_can_select_from_menu(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC, "choose", return_value=ENTRY),
            patch.object(OC, "shell_existing") as shell,
        ):
            OC.main(["shell"])
        shell.assert_called_once_with(ENTRY, False)

    def test_main_menu_can_open_terminal(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC, "choose", return_value=ENTRY),
            patch("builtins.input", return_value="t"),
            patch.object(OC, "shell_existing") as shell,
        ):
            OC.main([])
        shell.assert_called_once_with(ENTRY, False)

    def test_changed_agent_is_rejected(self):
        with patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "agent": "claude"}), patch.object(OC.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                OC.open_existing(ENTRY)
        run.assert_not_called()

    def test_stop_already_stopped_does_nothing(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.stop_existing(ENTRY)
        run.assert_not_called()

    def test_unknown_state_is_not_stopped(self):
        with patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "state": "unknown"}), patch.object(OC.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "uventet tilstand"):
                OC.stop_existing(ENTRY)
        run.assert_not_called()

    def test_stop_requires_confirmation_and_preserves_on_decline(self):
        with (
            patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "state": "running"}),
            patch.object(OC.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="n"),
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.stop_existing(ENTRY)
        run.assert_not_called()

    def test_confirmed_stop_only_stops_selected_sandbox(self):
        with (
            patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "state": "running"}),
            patch.object(OC.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="ja"),
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.stop_existing(ENTRY)
        self.assertEqual(run.call_args.args[0], ["sbx", "stop", "opencode-work"])

    def test_noninteractive_stop_is_rejected(self):
        with (
            patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "state": "running"}),
            patch.object(OC.sys.stdin, "isatty", return_value=False),
            patch.object(OC.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "Stopp krever"):
                OC.stop_existing(ENTRY)
        run.assert_not_called()

    def test_dry_run_stop_is_read_only(self):
        with (
            patch.object(OC.start, "inspect_sandbox", return_value={**INFO, "state": "running"}),
            patch("builtins.input") as ask,
            patch.object(OC.subprocess, "run") as run,
        ):
            OC.stop_existing(ENTRY, dry_run=True)
        ask.assert_not_called()
        run.assert_not_called()

    def test_menu_selects_and_opens(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", side_effect=["1", ""]),
            patch.object(OC, "open_existing") as open_existing,
        ):
            OC.main([])
        open_existing.assert_called_once_with(ENTRY, False, False)

    def test_menu_can_cancel(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="q"),
            patch.object(OC, "open_existing") as open_existing,
        ):
            OC.main([])
        open_existing.assert_not_called()

    def test_menu_can_choose_stop(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", side_effect=["1", "s"]),
            patch.object(OC, "stop_existing") as stop,
        ):
            OC.main([])
        stop.assert_called_once_with(ENTRY, False)

    def test_open_all_tabs_is_client_scoped(self):
        with patch.object(OC.start, "inspect_sandbox", return_value=INFO), patch.object(OC.subprocess, "run") as run:
            OC.open_existing(ENTRY, all_tabs=True)
        self.assertEqual(
            run.call_args.args[0][-2:],
            ["--env", 'OPENCODE_CLI_CONFIG_CONTENT={"tabs":{"mode":"on","scope":"global"}}'],
        )

    def test_invalid_option_combinations_fail_before_inventory(self):
        for args in (["stop", "--all-tabs"], ["shell", "--all-tabs"], ["list", "--name", "abc"], ["list", "extra"], [".", "extra"]):
            with self.subTest(args=args), patch.object(OC, "sandboxes") as inventory:
                with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                    OC.main(args)
                inventory.assert_not_called()

    def test_invalid_selection_and_empty_list_are_rejected(self):
        with self.assertRaises(ValueError):
            OC.choose([])
        with patch.object(OC.sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="0"):
            with self.assertRaises(ValueError):
                OC.choose([ENTRY])

    def test_list_only_reads_inventory(self):
        with patch.object(OC, "sandboxes", return_value=[ENTRY]), patch.object(OC.subprocess, "run") as run:
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                OC.main(["list"])
        self.assertIn("opencode-work [stopped]", out.getvalue())
        run.assert_not_called()

    def test_capabilities_current_project_does_not_call_sbx(self):
        with patch.object(OC.profiles, "show_plan") as show_plan, patch.object(OC, "sandboxes") as inventory:
            OC.main(["capabilities"])
        show_plan.assert_called_once_with(Path("."), OC.profiles.DEFAULT_CATALOG)
        inventory.assert_not_called()

    def test_capabilities_existing_sandbox_only_reads_metadata(self):
        with (
            patch.object(OC, "sandboxes", return_value=[ENTRY]),
            patch.object(OC.start, "inspect_sandbox", return_value=INFO),
            patch.object(OC.profiles, "show_plan") as show_plan,
        ):
            OC.main(["capabilities", "opencode-work"])
        show_plan.assert_called_once_with(WORKSPACE, OC.profiles.DEFAULT_CATALOG)

    def test_explicit_catalog_is_only_allowed_for_capabilities_or_project(self):
        with patch.object(OC.profiles, "show_plan") as show_plan:
            OC.main(["capabilities", str(WORKSPACE), "--catalog", "/trusted/catalog.json"])
        show_plan.assert_called_once_with(WORKSPACE, Path("/trusted/catalog.json"))
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            OC.main(["list", "--catalog", "/trusted/catalog.json"])
        with patch.object(OC, "sandboxes", return_value=[]), patch.object(OC.subprocess, "run") as run:
            OC.main([str(WORKSPACE), "--catalog", "/trusted/catalog.json", "--dry-run"])
        self.assertEqual(run.call_args.args[0][-2:], ["--catalog", "/trusted/catalog.json"])

    def test_unsafe_names_and_workspaces_are_rejected(self):
        for name in ("--rm", "bad name", "default"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                OC.named([ENTRY], name)
        for path in (Path.home(), Path("/")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                OC.project([], path, options())


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        runtime = ROOT / "tests/.runtime"
        runtime.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="project-identity-", dir=runtime)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *map(str, args)],
            check=True, capture_output=True, text=True, env=self.env, timeout=30,
        )

    def repository(self, name="project"):
        root = self.directory / name
        self.git("init", root)
        return root

    def test_root_and_subdirectory_share_identity(self):
        root = self.repository()
        directory = root / "src/package"
        directory.mkdir(parents=True)
        self.assertEqual(OC.project_workspace(root), root)
        self.assertEqual(OC.project_workspace(directory), root)
        self.assertEqual(OC.start.sandbox_name(OC.project_workspace(directory)), OC.start.sandbox_name(root))

    def test_real_git_discovery_delegates_root_and_start_directory(self):
        root = self.repository("project with spaces")
        directory = root / "src/package"
        directory.mkdir(parents=True)
        entry = {**ENTRY, "workspaces": [str(root)]}
        real_run = subprocess.run
        commands = []

        def run(command, **kwargs):
            if command[:2] == [sys.executable, str(ROOT / "start.py")]:
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)
            return real_run(command, **kwargs)

        with patch.object(OC.subprocess, "run", side_effect=run):
            OC.project([entry], root, options(dry_run=True))
            OC.project([entry], directory, options(dry_run=True))
        self.assertEqual(commands, [
            [sys.executable, str(ROOT / "start.py"), str(root), "--content",
             "--name", "opencode-work", "--dry-run"],
            [sys.executable, str(ROOT / "start.py"), str(root), "--content",
             "--workdir", str(directory), "--name", "opencode-work", "--dry-run"],
        ])

    def test_symlinked_directory_is_resolved_before_discovery(self):
        root = self.repository()
        directory = root / "src"
        directory.mkdir()
        link = self.directory / "alias"
        link.symlink_to(directory, target_is_directory=True)
        real_run = subprocess.run
        commands = []

        def run(command, **kwargs):
            if command[:2] == [sys.executable, str(ROOT / "start.py")]:
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)
            return real_run(command, **kwargs)

        with patch.object(OC.subprocess, "run", side_effect=run):
            OC.project([], link, options())
        self.assertEqual(commands, [
            [sys.executable, str(ROOT / "start.py"), str(root), "--content", "--workdir", str(directory)],
        ])

    def test_nested_repository_has_its_own_identity(self):
        root = self.repository()
        nested = root / "nested"
        self.git("init", nested)
        directory = nested / "src"
        directory.mkdir()
        self.assertEqual(OC.project_workspace(directory), nested)

    def test_non_git_uses_explicit_directory(self):
        # Midlertidigområdet er inne i dette repoet, så simuler grensen
        # til et ekte ikke-Git-område uten å skrive utenfor prosjektet.
        with patch.object(Path, "exists", return_value=False), patch.object(Path, "is_symlink", return_value=False):
            with patch.object(OC.subprocess, "run") as run:
                self.assertEqual(OC.project_workspace(self.directory), self.directory)
        run.assert_not_called()

    def test_inherited_git_overrides_are_ignored(self):
        root = self.repository()
        other = self.repository("other")
        with patch.dict(os.environ, {
            "GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other),
            "GIT_COMMON_DIR": str(other / ".git"), "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.bare", "GIT_CONFIG_VALUE_0": "true",
        }):
            self.assertEqual(OC.project_workspace(root), root)

    def test_broken_git_marker_fails_without_delegating(self):
        root = self.directory / "broken"
        root.mkdir()
        (root / ".git").write_text("gitdir: missing\n")
        with patch.object(OC.subprocess, "run", wraps=subprocess.run) as run:
            with self.assertRaisesRegex(ValueError, "Git-roten"):
                OC.project([], root, options())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], "git")

    def test_broken_git_symlink_fails_without_using_parent_repository(self):
        root = self.directory / "broken-link"
        root.mkdir()
        (root / ".git").symlink_to(root / "missing", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Git-roten"):
            OC.project_workspace(root)

    def test_configured_different_worktree_root_is_rejected(self):
        root = self.repository()
        other = self.directory / "other"
        other.mkdir()
        self.git("-C", root, "config", "core.worktree", other)
        with self.assertRaisesRegex(ValueError, "Git-roten avviker"):
            OC.project_workspace(root)

    def test_git_process_failure_does_not_fall_back_to_directory(self):
        root = self.repository()
        with patch.object(OC.subprocess, "run", side_effect=OSError("git unavailable")) as run:
            with self.assertRaises(OSError):
                OC.project([], root, options())
        self.assertEqual(run.call_count, 1)

    def test_linked_worktree_does_not_inherit_main_repository_mount(self):
        root = self.repository()
        self.git("-C", root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-m", "Fixture")
        linked = self.directory / "linked"
        self.git("-C", root, "worktree", "add", "-b", "linked", linked)
        self.assertNotEqual(OC.start.sandbox_name(root), OC.start.sandbox_name(linked))
        with self.assertRaisesRegex(ValueError, "Git-metadata utenfor"):
            OC.project_workspace(linked)
        # Hovedrepoet forblir et selvstendig prosjekt.
        self.assertEqual(OC.project_workspace(root), root)

    def test_external_git_directory_and_symlink_are_rejected(self):
        root = self.directory / "separate"
        metadata = self.directory / "metadata"
        self.git("init", "--separate-git-dir", metadata, root)
        with self.assertRaisesRegex(ValueError, "Git-metadata utenfor"):
            OC.project_workspace(root)
        (root / ".git").unlink()
        (root / ".git").symlink_to(metadata, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Git-metadata utenfor"):
            OC.project_workspace(root)


if __name__ == "__main__":
    unittest.main()
