import argparse
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
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
        self.assertEqual(run.call_args.args[0], [sys.executable, str(ROOT / "start.py"), str(WORKSPACE)])

    def test_explicit_name_is_preserved(self):
        args = options()
        args.name = "another"
        with patch.object(OC.subprocess, "run") as run:
            OC.project([ENTRY], WORKSPACE, args)
        self.assertEqual(run.call_args.args[0][-2:], ["--name", "another"])

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

    def test_unsafe_names_and_workspaces_are_rejected(self):
        for name in ("--rm", "bad name", "default"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                OC.named([ENTRY], name)
        for path in (Path.home(), Path("/")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                OC.project([], path, options())


if __name__ == "__main__":
    unittest.main()
