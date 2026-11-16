import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
START = runpy.run_path(str(ROOT / "start.py"))
MODELS = runpy.run_path(str(ROOT / "models/install.py"))
WORKSPACE = ROOT.parent


def sandbox_info():
    return {
        "agent": "opencode",
        "workspace": str(WORKSPACE),
        "kits": [str(ROOT / "personal"), str(ROOT / "models")],
        "secrets": [{"name": "anthropic"}, {"name": "berget"}],
        "host_mounts": [{
            "host_path": str(WORKSPACE),
            "container_target": str(WORKSPACE),
            "read_only": False,
        }],
    }


class StartTests(unittest.TestCase):
    def test_names_are_stable_and_distinguish_same_basename(self):
        name = START["sandbox_name"]
        self.assertEqual(name(Path("/a/project")), name(Path("/a/project")))
        self.assertNotEqual(name(Path("/a/project")), name(Path("/b/project")))
        self.assertLessEqual(len(name(Path("/a/" + "p" * 150))), 63)

    def test_existing_workspace_and_kits_must_match(self):
        validate = START["validate_existing"]
        validate(sandbox_info(), WORKSPACE)
        for change in (
            {"agent": "shell"},
            {"workspace": "/another/project"},
            {"kits": []},
            {"host_mounts": []},
            {"host_mounts": [
                *sandbox_info()["host_mounts"],
                {"host_path": "/another/project", "container_target": "/another/project", "read_only": False},
            ]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**sandbox_info(), **change}, WORKSPACE)

    def test_no_secret_registration_when_all_present(self):
        self.assertEqual(START["missing_secrets"](sandbox_info()), [])
        self.assertEqual(
            START["missing_secrets"]({"secrets": [{"name": "anthropic"}]}),
            ["berget"],
        )

    def test_reopen_does_not_create_or_transfer_secrets(self):
        responses = [
            subprocess.CompletedProcess([], 0, "opencode-work\n"),
            subprocess.CompletedProcess([], 0, json.dumps(sandbox_info())),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run:
            START["main"]([str(WORKSPACE), "--name", "opencode-work", "--all-tabs"])
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1][:4], ["sbx", "run", "--name", "opencode-work"])
        self.assertIn('OPENCODE_CLI_CONFIG_CONTENT={"tabs":{"mode":"on","scope":"global"}}', calls[-1])

    def test_new_dry_run_is_read_only(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "")) as run:
            START["main"]([str(WORKSPACE), "--dry-run"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["sbx", "ls", "-q"])

    def test_only_missing_key_is_registered(self):
        info = {**sandbox_info(), "secrets": [{"name": "anthropic"}]}
        responses = [
            subprocess.CompletedProcess([], 0, "opencode-work\n"),
            subprocess.CompletedProcess([], 0, json.dumps(info)),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run:
            START["main"]([str(WORKSPACE), "--name", "opencode-work", "--setup-only"])
        command = run.call_args.args[0]
        self.assertEqual(command[-2:], ["--provider", "berget"])

    def test_parent_directory_cannot_be_used_as_workdir(self):
        with self.assertRaises(ValueError):
            START["main"]([str(WORKSPACE), "--workdir", "..", "--dry-run"])

    def test_home_is_rejected(self):
        with self.assertRaises(ValueError):
            START["main"]([str(Path.home()), "--dry-run"])

    def test_lookup_error_does_not_create_sandbox(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["sbx", "ls"])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                START["main"]([str(WORKSPACE)])
        self.assertEqual(run.call_count, 1)


class ModelsTests(unittest.TestCase):
    def test_merge_preserves_settings_and_is_idempotent(self):
        merge = MODELS["merge_providers"]
        original = {"shell": "/usr/bin/zsh", "providers": {"openai": {}}}
        additions = {"berget": {"env": ["BERGET_API_KEY"]}}
        result = merge(original, additions)
        self.assertNotIn("berget", original["providers"])
        self.assertEqual(result["shell"], original["shell"])
        self.assertEqual(result["providers"]["openai"], {})
        self.assertEqual(merge(result, additions), result)

    def test_conflicts_are_rejected(self):
        for config in (
            {"providers": []},
            {"providers": {"berget": {"name": "existing"}}},
            {"provider": {"berget": {}}},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                MODELS["merge_providers"](config, {"berget": {}})


if __name__ == "__main__":
    unittest.main()
