import json
from pathlib import Path
import tempfile
import unittest

from sbx import logseq, mcp_runtime


class LogseqConnectionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / ".runtime"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def initialize(self):
        logseq.initialize(self.home, apply=True)

    def test_plan_never_writes_and_missing_profile_is_optional(self):
        plan = logseq.initialize(self.home)
        self.assertEqual(plan["connection"]["url"], "http://host.docker.internal:12320/mcp/")
        self.assertFalse(logseq.paths(self.home)[0].exists())
        self.assertIsNone(logseq.connection(self.home))

    def test_private_token_and_no_overwrite(self):
        self.initialize()
        _, token = logseq.paths(self.home)
        self.assertEqual(token.stat().st_mode & 0o777, 0o600)
        first = token.read_text()
        with self.assertRaises(ValueError):
            self.initialize()
        self.assertEqual(token.read_text(), first)
        self.assertNotIn(first.strip(), json.dumps(logseq.profile(self.home)))

    def test_public_token_and_workspace_state_are_refused(self):
        self.initialize()
        _, token = logseq.paths(self.home)
        token.chmod(0o644)
        with self.assertRaises(ValueError):
            logseq.connection(self.home)
        token.chmod(0o600)
        with self.assertRaises(ValueError):
            logseq.connection(self.home, self.home)

    def test_unreviewed_endpoint_and_token_path_are_refused(self):
        self.initialize()
        path, _ = logseq.paths(self.home)
        for field, value in (("url", "http://example.org/mcp"), ("tokenFile", "/unreviewed")):
            payload = logseq.profile(self.home)
            payload[field] = value
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                logseq.connection(self.home)

    def test_host_server_keeps_api_secret_out_of_arguments(self):
        self.initialize()
        path = self.home / ".config/opencode/opencode.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"mcp": {"servers": {"logseq": {
            "type": "local", "command": [str(self.home / ".local/bin/mcp-logseq")],
            "environment": {"LOGSEQ_API_URL": "http://127.0.0.1:12315",
                            "LOGSEQ_API_TOKEN": "synthetic-api-secret"},
        }}}}))
        command, env = logseq.server_process(self.home, {"UNRELATED_SECRET": "synthetic"})
        self.assertEqual(command[1:], ["--transport", "http", "--host", "127.0.0.1", "--port", "12320"])
        self.assertNotIn("synthetic-api-secret", " ".join(command))
        self.assertEqual(env["LOGSEQ_API_TOKEN"], "synthetic-api-secret")
        self.assertNotIn("UNRELATED_SECRET", env)
        self.assertNotEqual(env["MCP_HTTP_AUTH_TOKEN"], env["LOGSEQ_API_TOKEN"])

    def runtime(self):
        self.initialize()
        config = self.home / ".config/opencode/opencode.json"
        config.parent.mkdir(parents=True)
        original = {"providers": {"synthetic": {}}, "plugins": ["synthetic-plugin"],
                    "mcp": {"mcp-gateway": {"type": "remote", "url": "http://synthetic"}}}
        config.write_text(json.dumps(original))
        return config, original

    def test_runtime_preserves_unrelated_configuration_and_is_idempotent(self):
        path, original = self.runtime()
        remote = logseq.connection(self.home)
        self.assertTrue(mcp_runtime.configure(self.home, remote))
        value = json.loads(path.read_text())
        self.assertEqual(value["providers"], original["providers"])
        self.assertEqual(value["plugins"], original["plugins"])
        self.assertEqual(value["mcp"]["servers"]["mcp-gateway"], original["mcp"]["mcp-gateway"])
        self.assertEqual(value["mcp"]["servers"]["logseq"], remote)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        before = path.stat().st_mtime_ns
        self.assertFalse(mcp_runtime.configure(self.home, remote))
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_runtime_fails_before_mutation_with_invalid_permissions(self):
        path, original = self.runtime()
        original["permissions"] = {}
        path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            mcp_runtime.configure(self.home, logseq.connection(self.home))
        self.assertEqual(json.loads(path.read_text()), original)

    def test_runtime_refuses_conflict_and_symlink(self):
        path, original = self.runtime()
        original["mcp"]["logseq"] = {"type": "local", "command": ["unreviewed"]}
        path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            mcp_runtime.configure(self.home, logseq.connection(self.home))
        path.unlink()
        path.symlink_to(self.home / "elsewhere")
        with self.assertRaises(ValueError):
            mcp_runtime.configure(self.home, logseq.connection(self.home))

    def test_native_policy_denies_logseq_tools_and_resources_by_default(self):
        shared = mcp_runtime.native_permissions()
        self.assertIn(mcp_runtime.rule("logseq_*", "deny"), shared)
        self.assertIn(mcp_runtime.rule("opencode_list_mcp_resources", "deny", "logseq"), shared)
        self.assertIn(mcp_runtime.rule("opencode_read_mcp_resource", "deny", "logseq:*"), shared)
        self.assertTrue(all(r["effect"] == "deny" for r in shared))
        path, _ = self.runtime()
        mcp_runtime.configure(self.home, logseq.connection(self.home))
        self.assertNotIn("agents", json.loads(path.read_text()))

    def test_native_mcp_shape_and_unrelated_rules_are_preserved(self):
        path, original = self.runtime()
        original["mcp"] = {"servers": original["mcp"], "timeout": {"startup": 45000}}
        original["permissions"] = [mcp_runtime.rule("shell", "ask")]
        original["agents"] = {"reviewer": {"description": "Synthetic reviewer"}}
        path.write_text(json.dumps(original))
        mcp_runtime.configure(self.home, logseq.connection(self.home))
        value = json.loads(path.read_text())
        self.assertEqual(value["mcp"]["timeout"], original["mcp"]["timeout"])
        self.assertEqual(value["permissions"][0], original["permissions"][0])
        self.assertEqual(value["agents"]["reviewer"], original["agents"]["reviewer"])

    def test_invalid_endpoint_never_publishes_connection_or_rules(self):
        path, _ = self.runtime()
        before = path.read_bytes()
        remote = {**logseq.connection(self.home), "url": "https://example.org/mcp/"}
        with self.assertRaises(ValueError):
            mcp_runtime.configure(self.home, remote)
        self.assertEqual(path.read_bytes(), before)

    def test_existing_connection_with_missing_denial_is_not_silently_repaired(self):
        path, _ = self.runtime()
        remote = logseq.connection(self.home)
        mcp_runtime.configure(self.home, remote)
        value = json.loads(path.read_text())
        value["permissions"] = []
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            mcp_runtime.configure(self.home, remote)
        self.assertEqual(path.read_bytes(), before)
