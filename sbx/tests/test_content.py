import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    import content


class ContentTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parent / ".runtime"
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.source = self.root / "source"
        (self.source / "skills" / "alpha").mkdir(parents=True)
        (self.source / "skills" / "alpha" / "SKILL.md").write_text("skill")
        (self.source / "rules.md").write_text("rules")
        self.spec = {"source": str(self.source), "skills": ["skills"], "instructions": ["rules.md"]}

    def plan(self, spec=None, **kwargs):
        return content.build_plan(self.workspace, [("first", self.spec if spec is None else spec)], **kwargs)

    def test_multilayer_and_immutable(self):
        other = self.root / "other"
        (other / "abilities").mkdir(parents=True)
        (other / "abilities" / "beta.md").write_text("x")
        plan = content.build_plan(self.workspace, [
            ("first", self.spec), ("second", {"source": str(other), "skills": ["abilities"]}),
        ])
        self.assertEqual(plan.mounts, (content.Mount(self.source, "/opt/opencode-content/first"),
                                       content.Mount(other, "/opt/opencode-content/second")))
        self.assertEqual(plan.skills, ("/opt/opencode-content/first/skills",
                                       "/opt/opencode-content/second/abilities"))
        self.assertEqual(plan.instructions, ("/opt/opencode-content/first/rules.md",))
        self.assertIsNone(plan.agents)
        with self.assertRaises(AttributeError):
            plan.skills = ()

    def test_invalid_specs_and_paths(self):
        changes = [
            {"source": "/"}, {"source": str(Path.home())}, {"source": "relative"},
            {"source": str(self.root / "bad:name")}, {"skills": []}, {"skills": "skills"},
            {"skills": [None]}, {"skills": ["../source/skills"]}, {"skills": ["/skills"]},
            {"instructions": ["missing.md"]}, {"agents": "missing"}, {"unknown": True},
            {"defaultAgent": "alpha"}, {"skills": ["skills/../skills"]},
            {"skills": ["skills/"]}, {"skills": ["skills//alpha"]},
            {"instructions": ["rules.md", "rules.md"]},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.plan({**self.spec, **change})
        for layer in ("../bad", "Bad", "", "a--b"):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                content.build_plan(self.workspace, [(layer, self.spec)])
        with self.assertRaises(ValueError):
            content.build_plan(self.workspace, [("first", self.spec), ("second", self.spec)])

    def test_symlink_escape(self):
        (self.source / "outside").symlink_to("../workspace", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.plan({**self.spec, "skills": ["outside"]})
        (self.source / "skills" / "escape").symlink_to("../../workspace", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.plan()

    def test_absolute_and_broken_internal_links_are_rejected_before_creation(self):
        alias = self.source / "skills/alias"
        alias.symlink_to(self.source / "skills/alpha", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Absolute symlink"):
            self.plan()
        alias.unlink()
        alias.symlink_to("missing", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "broken"):
            self.plan()

    def test_project_skill_sources_are_checked_against_each_other(self):
        for folder in (".agents/skills/local", ".opencode/skills/local"):
            path = self.workspace / folder
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text("Fixture")
        with self.assertRaisesRegex(ValueError, "Duplicate skill ID: local"):
            self.plan()

    def test_duplicate_empty_skill_path_is_rejected(self):
        (self.source / "empty").mkdir()
        with self.assertRaisesRegex(ValueError, "Duplicate skills path"):
            self.plan({**self.spec, "skills": ["empty", "empty"]})

    def test_workspace_as_source_uses_project_paths_without_extra_mount(self):
        (self.source / "agents").mkdir()
        (self.source / "agents" / "main.md").write_text("agent")
        spec = {**self.spec, "agents": "agents", "defaultAgent": "main"}
        other = self.root / "other"
        (other / "abilities").mkdir(parents=True)
        (other / "abilities" / "beta.md").write_text("x")
        plan = content.build_plan(self.source, [
            ("first", spec), ("second", {"source": str(other), "skills": ["abilities"]}),
        ])
        self.assertEqual(plan.mounts, (content.Mount(other, "/opt/opencode-content/second"),))
        self.assertEqual(plan.workspace_root, str(self.source))
        self.assertEqual(plan.skills, (f"{self.source}/skills", "/opt/opencode-content/second/abilities"))
        self.assertEqual(plan.instructions, (f"{self.source}/rules.md",))
        self.assertEqual(plan.agents, f"{self.source}/agents")
        self.assertIsNone(self.plan().workspace_root)

    def test_content_target_cannot_overlap_project_target(self):
        with patch.object(Path, "is_dir", return_value=True):
            with self.assertRaisesRegex(ValueError, "overlaps"):
                content.build_plan(Path("/opt/opencode-content/first"), [("first", self.spec)])

    def test_skill_collisions_and_project_levels(self):
        (self.source / "skills" / "alpha.md").write_text("duplicate")
        with self.assertRaisesRegex(ValueError, "Duplicate skill ID: alpha"):
            self.plan()
        (self.source / "skills" / "alpha.md").unlink()
        nested = self.workspace / "nested"
        (nested / ".agents" / "skills" / "alpha").mkdir(parents=True)
        (nested / ".agents" / "skills" / "alpha" / "SKILL.md").write_text("duplicate")
        with self.assertRaisesRegex(ValueError, "Duplicate skill ID: alpha"):
            self.plan(directory=nested)
        self.plan()

    def test_discovery_depth_hidden_and_stops_at_skill(self):
        skills = self.source / "skills"
        (skills / "alpha" / "alpha.md").write_text("ignored inside skill")
        (skills / ".hidden" / "alpha").mkdir(parents=True)
        (skills / ".hidden" / "alpha" / "SKILL.md").write_text("ignored")
        (skills / "node_modules" / "alpha").mkdir(parents=True)
        (skills / "node_modules" / "alpha" / "SKILL.md").write_text("ignored")
        self.plan()
        nested = skills / "one" / "two" / "alpha"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("duplicate")
        with self.assertRaisesRegex(ValueError, "Duplicate skill ID"):
            self.plan()

    def test_agents_and_default(self):
        agents = self.source / "agents"
        agents.mkdir()
        (agents / "reviewer.md").write_text("agent")
        spec = {**self.spec, "agents": "agents", "defaultAgent": "reviewer"}
        plan = self.plan(spec)
        self.assertEqual(plan.agents, "/opt/opencode-content/first/agents")
        self.assertEqual(plan.default_agent, "reviewer")
        with self.assertRaises(ValueError):
            self.plan({**spec, "defaultAgent": "missing"})
        project = self.workspace / ".opencode" / "agents"
        project.mkdir(parents=True)
        (project / "reviewer.md").write_text("collision")
        with self.assertRaisesRegex(ValueError, "Duplicate agent ID"):
            self.plan(spec)

    def test_grouped_agent_ids_and_root_default(self):
        agents = self.source / "agents"
        (agents / "team").mkdir(parents=True)
        (agents / "team" / "reviewer.md").write_text("grouped")
        (agents / "team" / "main.md").write_text("grouped main")
        (agents / "reviewer.md").write_text("root")
        spec = {**self.spec, "agents": "agents"}
        self.plan(spec)
        with self.assertRaisesRegex(ValueError, "corresponding agent"):
            self.plan({**spec, "defaultAgent": "main"})
        (agents / "main.md").write_text("root main")
        self.assertEqual(self.plan({**spec, "defaultAgent": "main"}).default_agent, "main")
        project = self.workspace / ".opencode" / "agents" / "other"
        project.mkdir(parents=True)
        (project / "reviewer.md").write_text("different group")
        self.plan(spec)
        (project.parent / "team").mkdir()
        (project.parent / "team" / "reviewer.md").write_text("same group")
        with self.assertRaisesRegex(ValueError, "Duplicate agent ID: team/reviewer"):
            self.plan(spec)

    def test_duplicate_instruction_alias(self):
        (self.source / "alias.md").symlink_to("rules.md")
        with self.assertRaisesRegex(ValueError, "Duplicate instruction path"):
            self.plan({**self.spec, "instructions": ["rules.md", "alias.md"]})

    def test_no_mutation(self):
        before = {p.relative_to(self.root): (p.read_bytes() if p.is_file() else None)
                  for p in self.root.rglob("*")}
        spec = copy.deepcopy(self.spec)
        self.plan(spec)
        self.assertEqual(spec, self.spec)
        after = {p.relative_to(self.root): (p.read_bytes() if p.is_file() else None)
                 for p in self.root.rglob("*")}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
