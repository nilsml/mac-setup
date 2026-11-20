import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SBX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SBX))
import mcp
import mcp_host


class McpTest(unittest.TestCase):
    def setUp(self):
        runtime = SBX / "tests/.runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / ".config/opencode/opencode.json"
        self.config.parent.mkdir(parents=True)
        self.server = {
            "type": "local",
            "command": [str(self.home / ".local/bin/browse"), "mcp"],
            "environment": {"OPENCODE_BROWSER_RUNTIME": "auto-update"},
        }
        self.save()

    def save(self):
        self.config.write_text(json.dumps({"mcp": {"servers": {"browse": self.server}}}))

    def test_fixed_command_and_environment_filter(self):
        command, env = mcp_host.browse_process(self.home, {
            "PATH": "/bin", "LOGSEQ_API_TOKEN": "synthetic", "OPENAI_API_KEY": "synthetic",
        })
        self.assertEqual(command, self.server["command"])
        self.assertEqual(env, {
            "HOME": str(self.home), "PATH": "/bin", "OPENCODE_BROWSER_RUNTIME": "auto-update",
        })

    def test_arbitrary_command_refused(self):
        self.server["command"] = ["/bin/sh", "-c", "false"]
        self.save()
        with self.assertRaises(ValueError):
            mcp_host.browse_process(self.home, {})

    def test_extra_environment_refused(self):
        self.server["environment"]["LOGSEQ_API_TOKEN"] = "synthetic"
        self.save()
        with self.assertRaises(ValueError):
            mcp_host.browse_process(self.home, {})

    def test_disabled_or_jsonc_refused(self):
        self.server["disabled"] = True
        self.save()
        with self.assertRaises(ValueError):
            mcp_host.browse_process(self.home, {})
        self.server["disabled"] = False
        self.save()
        self.config.with_suffix(".jsonc").write_text("{}")
        with self.assertRaises(ValueError):
            mcp_host.browse_process(self.home, {})

    def test_plan_has_no_side_effects(self):
        with patch.object(mcp.subprocess, "run") as run:
            plan = mcp.browse_plan(self.home)
        run.assert_not_called()
        self.assertEqual(len(plan), 1)
        self.assertNotIn("logseq", json.dumps(plan))

    def test_relative_launcher_refused(self):
        for name in ("--help", "name/path", "name space", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                mcp.browse_plan(name)

    def test_default_plan_registers_globally_without_sandbox(self):
        with patch.object(mcp.subprocess, "run") as run:
            plan = mcp.browse_plan(launcher=self.home)
        run.assert_not_called()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][:5], ["sbx", "mcp", "add", "browse", "--command"])
        self.assertNotIn("--sandbox", plan[0])

    def test_default_browse_runner_is_beside_registration_script(self):
        plan = mcp.browse_plan()
        self.assertIn(f"{SBX / 'mcp_host.py'},browse", plan[0])

    def test_symlinked_launcher_path_is_kept(self):
        (self.home / "launcher-v9").mkdir()
        (self.home / "launcher-current").symlink_to("launcher-v9", target_is_directory=True)
        plan = mcp.browse_plan(launcher=self.home / "launcher-current")
        self.assertIn(f"{self.home / 'launcher-current' / 'mcp_host.py'},browse", plan[0])

    def test_global_registration_does_not_inspect_or_load_sandbox(self):
        (self.home / "mcp_host.py").write_text("# synthetic")
        with patch.object(mcp.subprocess, "run") as run:
            run.return_value.stdout = ""
            mcp.activate_browse(launcher=self.home)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][:4], ["sbx", "mcp", "add", "browse"])

    def test_rovo_uses_official_gateway_endpoint_without_automatic_login(self):
        plan = mcp.registration_plan("rovo")
        self.assertEqual(plan, [[
            "sbx", "mcp", "add", "rovo", "--url",
            "https://mcp.atlassian.com/v2/mcp", "--skip-auth",
        ]])

    def test_restricted_logseq_cannot_be_registered_in_public_catalog(self):
        with self.assertRaises(ValueError):
            mcp.registration_plan("logseq")

    def test_existing_registration_not_replaced(self):
        (self.home / "mcp_host.py").write_text("# synthetic")
        with patch.object(mcp.subprocess, "run") as run:
            run.return_value.stdout = "browse\n"
            with self.assertRaises(ValueError):
                mcp.activate_browse(self.home)
            self.assertEqual(run.call_count, 1)

    def test_missing_launcher_refused_before_registration(self):
        with patch.object(mcp.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                mcp.activate_browse(self.home)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
