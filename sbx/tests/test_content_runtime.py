import json
from pathlib import Path
import tempfile
import unittest

from sbx.content_runtime import check, configure
from sbx import mcp_runtime


class ContentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.mount = self.base / "mount"
        self.home.mkdir()
        (self.mount / "skills/demo").mkdir(parents=True)
        (self.mount / "skills/demo/SKILL.md").write_text("skill")
        (self.mount / "instructions").mkdir()
        (self.mount / "instructions/team.md").write_text("instruction")
        (self.mount / "agents").mkdir()
        (self.mount / "agents/reviewer.md").write_text("agent")
        self.payload = {
            "skills": [str(self.mount / "skills")],
            "instructions": [str(self.mount / "instructions/team.md")],
            "agents": str(self.mount / "agents"),
            "default_agent": "reviewer",
        }

    def tearDown(self):
        self.temp.cleanup()

    @property
    def config(self):
        return self.home / ".config/opencode/opencode.json"

    def test_preserves_existing_configuration_and_registers_live_content(self):
        self.config.parent.mkdir(parents=True)
        original = {
            "provider": {"local": {"options": {"apiKey": "secret"}}},
            "plugins": ["manual-plugin"],
            "instructions": ["manual.md"],
            "model": "local/model",
        }
        self.config.write_text(json.dumps(original))
        configure(self.home, self.payload, self.mount)
        config = json.loads(self.config.read_text())
        self.assertEqual(config["provider"], original["provider"])
        self.assertEqual(config["plugins"], original["plugins"])
        self.assertEqual(config["model"], original["model"])
        self.assertEqual(config["instructions"], ["manual.md", *self.payload["instructions"]])
        self.assertEqual(config["skills"], self.payload["skills"])
        self.assertEqual(config["default_agent"], "reviewer")
        self.assertEqual((self.home / ".config/opencode/agents").resolve(), (self.mount / "agents").resolve())
        self.assertEqual(json.loads((self.home / ".local/state/opencode-sbx/content.json").read_text()), self.payload)
        self.assertTrue(check(self.home, self.payload, self.mount))

    def test_idempotent(self):
        configure(self.home, self.payload, self.mount)
        before = self.config.stat().st_mtime_ns
        configure(self.home, self.payload, self.mount)
        self.assertEqual(before, self.config.stat().st_mtime_ns)

    def test_logseq_setup_keeps_live_agents_and_reopen_content_check_valid(self):
        (self.mount / "agents/logseq.md").write_text(
            "---\nmode: all\npermissions:\n"
            '  - action: "*"\n    resource: "*"\n    effect: deny\n'
            '  - action: logseq_*\n    resource: "*"\n    effect: allow\n'
            "---\nSynthetic Logseq agent\n"
        )
        configure(self.home, self.payload, self.mount)
        remote = {
            "type": "remote", "url": "http://host.docker.internal:12320/mcp/",
            "oauth": False, "headers": {"Authorization": "Bearer " + "s" * 32},
        }
        mcp_runtime.configure(self.home, remote)
        self.assertTrue(check(self.home, self.payload, self.mount))
        self.assertNotIn("agents", json.loads(self.config.read_text()))
        self.assertTrue((self.home / ".config/opencode/agents/logseq.md").is_file())

    def test_conflicts_fail_before_mutation(self):
        self.config.parent.mkdir(parents=True)
        original = {"default_agent": "other"}
        self.config.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            configure(self.home, self.payload, self.mount)
        self.assertEqual(json.loads(self.config.read_text()), original)
        self.assertFalse((self.home / ".config/opencode/agents").exists())

    def test_rejects_jsonc_and_duplicate_json_keys(self):
        root = self.home / ".config/opencode"
        root.mkdir(parents=True)
        (root / "opencode.jsonc").write_text("{}")
        with self.assertRaises(ValueError):
            configure(self.home, self.payload, self.mount)
        (root / "opencode.jsonc").unlink()
        self.config.write_text('{"model":"a","model":"b"}')
        with self.assertRaises(ValueError):
            configure(self.home, self.payload, self.mount)

    def test_rejects_bad_and_escaping_paths(self):
        bad = dict(self.payload, skills=[str(self.base / "outside")])
        with self.assertRaises(ValueError):
            configure(self.home, bad, self.mount)
        escape = self.mount / "skills/escape"
        escape.symlink_to(self.base, target_is_directory=True)
        bad = dict(self.payload, skills=[str(escape)])
        with self.assertRaises(ValueError):
            configure(self.home, bad, self.mount)
        self.assertFalse(self.config.exists())

    def test_existing_agents_path_is_never_overwritten(self):
        target = self.home / ".config/opencode/agents"
        target.mkdir(parents=True)
        with self.assertRaises(ValueError):
            configure(self.home, self.payload, self.mount)
        self.assertTrue(target.is_dir())
        self.assertFalse(self.config.exists())

    def test_check_detects_drift(self):
        configure(self.home, self.payload, self.mount)
        config = json.loads(self.config.read_text())
        config["model"] = "changed"
        self.config.write_text(json.dumps(config))
        # Unrelated settings are preserved and do not constitute content drift.
        self.assertTrue(check(self.home, self.payload, self.mount))
        config["skills"] = []
        self.config.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            check(self.home, self.payload, self.mount)

    def test_check_is_read_only(self):
        configure(self.home, self.payload, self.mount)
        paths = [
            self.config,
            self.home / ".config/opencode/agents",
            self.home / ".local/state/opencode-sbx/content.json",
        ]
        before = [(p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else str(p.resolve()))
                  for p in paths]
        self.assertTrue(check(self.home, self.payload, self.mount))
        after = [(p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else str(p.resolve()))
                 for p in paths]
        self.assertEqual(before, after)

    def test_default_agent_must_be_direct_markdown_file(self):
        (self.mount / "agents/reviewer.md").unlink()
        (self.mount / "agents/group").mkdir()
        (self.mount / "agents/group/reviewer.md").write_text("nested")
        with self.assertRaisesRegex(ValueError, "default_agent Markdown"):
            configure(self.home, self.payload, self.mount)

    def test_rejects_external_flat_skill_markdown_symlink(self):
        outside = self.base / "outside.md"
        outside.write_text("outside")
        (self.mount / "skills/leak.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes source"):
            configure(self.home, self.payload, self.mount)

    def test_checks_compatibility_skill_directories_and_configured_agents(self):
        compatibility = self.home / ".agents/skills"
        (compatibility / "demo").mkdir(parents=True)
        (compatibility / "demo/SKILL.md").write_text("collision")
        with self.assertRaisesRegex(ValueError, "conflicts with existing global skill"):
            configure(self.home, self.payload, self.mount)
        (compatibility / "demo/SKILL.md").unlink()
        (compatibility / "demo").rmdir()
        compatibility.rmdir()

        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({"agents": {"reviewer": {"mode": "primary"}}}))
        # Configured IDs are path-based. A grouped file is team/reviewer, not reviewer.
        (self.mount / "agents/reviewer.md").rename(self.mount / "agents/old-reviewer.md")
        (self.mount / "agents/team").mkdir()
        (self.mount / "agents/team/reviewer.md").write_text("agent")
        grouped_payload = dict(self.payload, default_agent=None)
        configure(self.home, grouped_payload, self.mount)
        self.config.write_text(json.dumps({"agents": {"team/reviewer": {"mode": "primary"}}}))
        with self.assertRaisesRegex(ValueError, "conflicts with configured agent: team/reviewer"):
            configure(self.home, grouped_payload, self.mount)
        self.assertTrue((self.home / ".config/opencode/agents").is_symlink())

    def test_rejects_symlinked_compatibility_skill_directory(self):
        real = self.base / "real-skills"
        real.mkdir()
        (self.home / ".claude").mkdir()
        (self.home / ".claude/skills").symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked compatibility"):
            configure(self.home, self.payload, self.mount)

    def test_agent_ids_use_grouped_relative_path_and_reject_bad_symlinks(self):
        (self.mount / "agents/reviewer.md").rename(self.mount / "agents/old-reviewer.md")
        (self.mount / "agents/team").mkdir()
        (self.mount / "agents/team/reviewer.md").write_text("agent")
        grouped_payload = dict(self.payload, default_agent=None)
        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({"agents": {"reviewer": {}}}))
        configure(self.home, grouped_payload, self.mount)
        self.config.write_text(json.dumps({"agents": {"team/reviewer": {}}}))
        with self.assertRaisesRegex(ValueError, "team/reviewer"):
            configure(self.home, grouped_payload, self.mount)

        self.config.write_text("{}")
        outside = self.base / "outside-agent.md"
        outside.write_text("external")
        (self.mount / "agents/leak.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes content root"):
            configure(self.home, grouped_payload, self.mount)

    def test_rejects_broken_and_escaping_skill_symlinks(self):
        broken = self.mount / "skills/broken.md"
        broken.symlink_to(self.base / "missing.md")
        with self.assertRaisesRegex(ValueError, "Broken skill symlink"):
            configure(self.home, self.payload, self.mount)
        broken.unlink()
        external_dir = self.base / "external-skills"
        external_dir.mkdir()
        (external_dir / "extra.md").write_text("external")
        (self.mount / "skills/external-dir").symlink_to(external_dir, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes source"):
            configure(self.home, self.payload, self.mount)

    def test_check_detects_agent_and_skill_symlink_drift(self):
        configure(self.home, self.payload, self.mount)
        agents_link = self.home / ".config/opencode/agents"
        replacement = self.mount / "replacement-agents"
        replacement.mkdir()
        (replacement / "reviewer.md").write_text("agent")
        agents_link.unlink()
        agents_link.symlink_to(replacement, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Agents symlink"):
            check(self.home, self.payload, self.mount)

        agents_link.unlink()
        agents_link.symlink_to(self.mount / "agents", target_is_directory=True)
        external = self.base / "external.md"
        external.write_text("outside")
        skill_link = self.mount / "skills/outside.md"
        skill_link.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "escapes source"):
            check(self.home, self.payload, self.mount)

    def test_legacy_agent_config_requires_manual_review(self):
        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({"agent": {"reviewer": {}}}))
        with self.assertRaisesRegex(ValueError, "legacy-config-review"):
            configure(self.home, self.payload, self.mount)

    def test_rolls_back_created_link_when_write_fails(self):
        # A directory where the marker file belongs causes the final atomic write to fail.
        (self.home / ".local/state/opencode-sbx/content.json").mkdir(parents=True)
        with self.assertRaises((ValueError, IsADirectoryError, OSError)):
            configure(self.home, self.payload, self.mount)
        self.assertFalse((self.home / ".config/opencode/agents").exists())
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
