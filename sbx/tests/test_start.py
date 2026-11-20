import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT), *sys.path]):
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
    def setUp(self):
        connection = patch.object(START["logseq"], "connection", return_value=None)
        connection.start()
        self.addCleanup(connection.stop)

    def test_new_sandbox_uses_dynamic_mcp_catalog(self):
        create, _ = START["inspect_commands"](WORKSPACE, "test-sandbox", WORKSPACE, False)
        self.assertNotIn("--static-mcp", create)

    def test_new_sandbox_always_pulls_images_without_changing_reopen(self):
        create, attach = START["inspect_commands"](WORKSPACE, "test-sandbox", WORKSPACE, False)
        index = create.index("--pull")
        self.assertEqual(create[index + 1], "always")
        self.assertNotIn("--pull", attach)

    def test_new_sandbox_removes_upstream_inline_allow_all_override(self):
        create, attach = START["inspect_commands"](WORKSPACE, "test-sandbox", WORKSPACE, False)
        index = create.index("--env")
        self.assertEqual(create[index + 1], "OPENCODE_CONFIG_CONTENT={}")
        self.assertNotIn("OPENCODE_CONFIG_CONTENT={}", attach)

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

    def test_kits_from_earlier_installed_launcher_are_accepted(self):
        validate = START["validate_existing"]
        earlier = START["LAUNCHERS"] / "launcher-earlier"
        validate({**sandbox_info(), "kits": [str(earlier / "personal"), str(earlier / "models")]}, WORKSPACE)
        other = START["LAUNCHERS"] / "launcher-other"
        for kits in (
            [str(earlier / "personal"), str(other / "models")],
            [str(earlier / "personal")],
            ["/old/launcher/personal", "/old/launcher/models"],
            [str(START["LAUNCHERS"] / "nested/launcher/personal"),
             str(START["LAUNCHERS"] / "nested/launcher/models")],
        ):
            with self.subTest(kits=kits), self.assertRaises(ValueError):
                validate({**sandbox_info(), "kits": kits}, WORKSPACE)

    def test_malformed_mount_metadata_is_rejected_cleanly(self):
        for mounts in (None, "invalid", [None], ["invalid"],
                       [{**sandbox_info()["host_mounts"][0], "container_target": {}}],
                       [{**sandbox_info()["host_mounts"][0], "read_only": 1}]):
            with self.subTest(mounts=mounts), self.assertRaises(ValueError):
                START["validate_existing"]({**sandbox_info(), "host_mounts": mounts}, WORKSPACE)

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


class ContentStartTests(unittest.TestCase):
    def setUp(self):
        connection = patch.object(START["logseq"], "connection", return_value=None)
        connection.start()
        self.addCleanup(connection.stop)
        runtime = ROOT / "tests/.runtime"
        runtime.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.workspace = self.base / "project"
        self.source = self.base / "content"
        for path in (self.workspace, self.source / "skills/probe", self.source / "agents"):
            path.mkdir(parents=True)
        (self.source / "skills/probe/SKILL.md").write_text("---\ndescription: Fixture\n---\nProbe\n")
        (self.source / "agents/main.md").write_text("---\nmode: primary\n---\nFixture\n")
        (self.source / "rules.md").write_text("Fixture rules\n")
        self.spec = {
            "source": str(self.source), "skills": ["skills"],
            "agents": "agents", "instructions": ["rules.md"], "defaultAgent": "main",
        }
        self.catalog = self.base / "catalog.json"
        self.catalog.write_text(json.dumps({
            "schemaVersion": 2, "layers": [{
                "id": "personal", "scope": {"type": "always"}, "requires": [], "content": self.spec,
            }],
        }))
        self.plan = START["selected_content"](self.workspace, self.workspace, self.catalog)
        self.args = [str(self.workspace), "--name", "content-test", "--content", "--catalog", str(self.catalog)]
        self.info = {
            **sandbox_info(), "workspace": str(self.workspace),
            "host_mounts": [{
                "host_path": str(self.workspace), "container_target": str(self.workspace), "read_only": False,
            }, {
                "host_path": str(self.source), "container_target": "/opt/opencode-content/personal", "read_only": True,
            }],
        }

    def test_new_content_dry_run_lists_mount_and_does_not_execute(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "")) as run:
            START["main"]([*self.args, "--dry-run"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["sbx", "ls", "-q"])

    def test_create_uses_readonly_positional_mount_and_configures_before_attach(self):
        responses = [
            subprocess.CompletedProcess([], 0, ""),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, json.dumps(self.info)),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run, \
                patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="ja"):
            START["main"](self.args)
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[1][0:5], [
            "sbx", "create", "opencode", str(self.workspace),
            f"{self.source}:/opt/opencode-content/personal:ro",
        ])
        self.assertEqual(calls[3][:7], ["sbx", "exec", "-u", "agent", "content-test", "python3", "-c"])
        self.assertEqual(json.loads(run.call_args_list[3].kwargs["input"]), START["content_payload"](self.plan))
        self.assertEqual(calls[4], ["sbx", "run", "--name", "content-test", "--workdir", str(self.workspace)])

    def test_new_environment_receives_private_logseq_connection_over_stdin_only(self):
        remote = {"type": "remote", "url": "http://host.docker.internal:12320/mcp/",
                  "oauth": False, "headers": {"Authorization": "Bearer synthetic-private-token"}}
        responses = [
            subprocess.CompletedProcess([], 0, ""),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, json.dumps(self.info)),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run, \
                patch.object(START["logseq"], "connection", return_value=remote), \
                patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="ja"):
            START["main"](self.args)
        call = run.call_args_list[4]
        self.assertEqual(call.args[0][:6], ["sbx", "exec", "-i", "-u", "agent", "content-test"])
        self.assertNotIn("synthetic-private-token", " ".join(call.args[0]))
        self.assertEqual(json.loads(call.kwargs["input"]), remote)
        self.assertEqual(run.call_args.args[0][:2], ["sbx", "run"])

    def test_existing_content_is_checked_without_reconfiguring(self):
        responses = [
            subprocess.CompletedProcess([], 0, "content-test\n"),
            subprocess.CompletedProcess([], 0, json.dumps(self.info)),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run, \
                patch.object(START["logseq"], "connection") as connection:
            START["main"]([*self.args, "--setup-only"])
        connection.assert_not_called()
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[0][-1], "--check")

    def test_legacy_environment_ignores_content_catalog_and_is_not_reconfigured(self):
        info = {
            **self.info, "host_mounts": self.info["host_mounts"][:1],
            "kits": ["/old/launcher/personal", "/old/launcher/models"], "secrets": [],
        }
        self.catalog.unlink()
        responses = [
            subprocess.CompletedProcess([], 0, "content-test\n"),
            subprocess.CompletedProcess([], 0, json.dumps(info)),
        ]
        with patch("subprocess.run", side_effect=responses) as run:
            START["main"]([*self.args, "--setup-only"])
        self.assertEqual(run.call_count, 2)

    def workspace_catalog(self):
        catalog = self.base / "workspace-catalog.json"
        catalog.write_text(json.dumps({
            "schemaVersion": 2, "layers": [{
                "id": "personal", "scope": {"type": "always"}, "requires": [],
                "content": {**self.spec, "source": str(self.source)},
            }],
        }))
        info = {**self.info, "workspace": str(self.source), "host_mounts": [{
            "host_path": str(self.source), "container_target": str(self.source), "read_only": False,
        }]}
        args = [str(self.source), "--name", "content-test", "--content", "--catalog", str(catalog)]
        return args, info

    def test_workspace_as_content_source_has_no_conflicting_readonly_mount(self):
        args, info = self.workspace_catalog()
        responses = [
            subprocess.CompletedProcess([], 0, ""),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, json.dumps(info)),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run, \
                patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="ja"):
            START["main"](args)
        create = run.call_args_list[1].args[0]
        self.assertEqual(create[:4], ["sbx", "create", "opencode", str(self.source)])
        self.assertFalse(any(part.endswith(":ro") for part in create))
        payload = json.loads(run.call_args_list[3].kwargs["input"])
        self.assertEqual(payload["workspace"], str(self.source))
        self.assertEqual(payload["skills"], [f"{self.source}/skills"])

    def test_reopened_workspace_content_is_checked_not_treated_as_legacy(self):
        args, info = self.workspace_catalog()
        responses = [
            subprocess.CompletedProcess([], 0, "content-test\n"),
            subprocess.CompletedProcess([], 0, json.dumps(info)),
            subprocess.CompletedProcess([], 0),
        ]
        with patch("subprocess.run", side_effect=responses) as run:
            START["main"]([*args, "--setup-only"])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[0][-1], "--check")

    def test_mount_check_rejects_readwrite_extra_missing_and_duplicate_mounts(self):
        for mounts in (
            self.info["host_mounts"][:1],
            [*self.info["host_mounts"], self.info["host_mounts"][1]],
            [self.info["host_mounts"][0], {**self.info["host_mounts"][1], "read_only": False}],
            [self.info["host_mounts"][0], {**self.info["host_mounts"][1], "container_target": "/different"}],
        ):
            with self.subTest(mounts=mounts), self.assertRaises(ValueError):
                START["validate_existing"]({**self.info, "host_mounts": mounts}, self.workspace, self.plan)

    def test_unknown_extra_mount_does_not_pass_validation(self):
        with self.assertRaises(ValueError):
            START["validate_existing"](self.info, self.workspace)

    def test_old_catalog_fails_before_creation(self):
        self.catalog.write_text(json.dumps({
            "schemaVersion": 1, "layers": [{
                "id": "personal", "scope": {"type": "always"}, "requires": [],
            }],
        }))
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "")) as run:
            with self.assertRaisesRegex(ValueError, "katalogformat 2"):
                START["main"](self.args)
        self.assertEqual(run.call_count, 1)

    def test_catalog_inside_workspace_is_rejected(self):
        catalog = self.workspace / "catalog.json"
        catalog.write_text(self.catalog.read_text())
        with self.assertRaisesRegex(ValueError, "utenfor"):
            START["selected_content"](self.workspace, self.workspace, catalog)

    def test_launcher_inside_workspace_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "utenfor"):
            START["selected_content"](ROOT.parent, ROOT, self.catalog)

    def test_declining_creation_does_not_create_or_configure(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "")) as run, \
                patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="nei"):
            with self.assertRaisesRegex(ValueError, "Avbrutt"):
                START["main"](self.args)
        self.assertEqual(run.call_count, 1)

    def test_content_failure_does_not_delete_created_environment(self):
        responses = [
            subprocess.CompletedProcess([], 0, ""),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0, json.dumps(self.info)),
            subprocess.CalledProcessError(1, ["sbx", "exec"]),
        ]
        with patch("subprocess.run", side_effect=responses) as run, \
                patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="ja"):
            with self.assertRaisesRegex(ValueError, "Miljøet er beholdt"):
                START["main"](self.args)
        self.assertEqual(run.call_count, 4)
        self.assertTrue(all("rm" not in call.args[0] for call in run.call_args_list))


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

    def test_default_model_is_fallback_only(self):
        default = MODELS["with_default_model"]
        original = {"shell": "/usr/bin/zsh"}
        self.assertEqual(default(original), {**original, "model": "openai/gpt-6.2-sol"})
        self.assertNotIn("model", original)
        chosen = {"model": "anthropic/claude-opus-5-5"}
        self.assertIs(default(chosen), chosen)
        with self.assertRaises(ValueError):
            default({"model": {"id": "x"}})

    def test_provider_policies_are_appended_once(self):
        apply = MODELS["with_provider_policies"]
        earlier = {"action": "provider.use", "resource": "groq", "effect": "allow"}
        original = {"shell": "/usr/bin/zsh", "policies": [earlier]}
        result = apply(original)
        self.assertEqual(original["policies"], [earlier])
        self.assertEqual(result["policies"][0], earlier)
        self.assertEqual(
            result["policies"][1],
            {"action": "provider.use", "resource": "*", "effect": "deny"},
        )
        allowed = [rule["resource"] for rule in result["policies"][2:]]
        self.assertEqual(allowed, ["openai", "anthropic", "berget", "opencode"])
        self.assertIs(apply(result), result)
        with self.assertRaises(ValueError):
            apply({"policies": {}})


if __name__ == "__main__":
    unittest.main()
