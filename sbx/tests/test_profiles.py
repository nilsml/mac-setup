import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
    import profiles


class ProfileTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parent / ".runtime"
        runtime.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name).resolve() / "home"
        self.work = self.home / "work"
        self.repo = self.work / "product"
        self.nested = self.repo / "src"
        self.outside = self.home / "personal"
        for path in (self.nested, self.outside):
            path.mkdir(parents=True)
        self.origin = "https://example.invalid/team/product.git"
        self.catalog = {
            "schemaVersion": 1,
            "layers": [
                {"id": "personal", "scope": {"type": "always"}, "requires": []},
                {"id": "work", "scope": {"type": "directory", "path": "~/work"}, "requires": ["personal"]},
                {"id": "product", "scope": {
                    "type": "repository", "path": "~/work/product", "origin": self.origin,
                }, "requires": ["personal", "work"]},
            ],
        }

    def layers(self):
        return profiles.parse_catalog(self.catalog, self.home)

    def select(self, path):
        return [layer.id for layer in profiles.select_layers(
            path, self.layers(), identity=lambda _: (self.repo, self.origin),
        )]

    def test_personal_everywhere(self):
        self.assertEqual(self.select(self.outside), ["personal"])

    def test_format_two_keeps_same_routing_and_carries_content(self):
        self.catalog["schemaVersion"] = 2
        for layer in self.catalog["layers"]:
            layer["content"] = {"source": f"~/content/{layer['id']}", "skills": ["skills"]}
        self.assertEqual(self.select(self.repo), ["personal", "work", "product"])
        self.assertEqual(self.layers()[0].content, {"source": "~/content/personal", "skills": ["skills"]})

    def test_format_two_requires_content_object_for_every_layer(self):
        self.catalog["schemaVersion"] = 2
        for layer in self.catalog["layers"]:
            layer["content"] = None
        with self.assertRaisesRegex(ValueError, "content"):
            self.layers()

    def test_work_root_and_children(self):
        self.assertEqual(self.select(self.work), ["personal", "work"])
        child = self.work / "another"
        child.mkdir()
        self.assertEqual(self.select(child), ["personal", "work"])

    def test_repository_root_and_children(self):
        for path in (self.repo, self.nested):
            self.assertEqual(self.select(path), ["personal", "work", "product"])

    def test_parent_mount_does_not_activate_child_repository(self):
        for path, expected in ((self.home, ["personal"]), (self.work, ["personal", "work"])):
            with patch.object(profiles, "repository_identity", side_effect=AssertionError("No Git needed")) as identity:
                selected = profiles.select_layers(path, self.layers(), identity=identity)
            self.assertEqual([layer.id for layer in selected], expected)
            identity.assert_not_called()

    def test_same_basename_elsewhere_does_not_activate_product(self):
        other = self.outside / "product"
        other.mkdir()
        self.assertEqual(self.select(other), ["personal"])

    def test_directory_prefix_is_not_a_path_boundary(self):
        other = self.home / "work-extra"
        other.mkdir()
        self.assertEqual(self.select(other), ["personal"])

    def test_symlink_uses_actual_location(self):
        alias = self.outside / "link"
        alias.symlink_to(self.nested, target_is_directory=True)
        self.assertEqual(self.select(alias), ["personal", "work", "product"])

    def test_replaced_repository_or_wrong_origin_fails_closed(self):
        for identity in ((self.work, self.origin), (self.repo, "https://example.invalid/other.git")):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "identity mismatch"):
                profiles.select_layers(self.repo, self.layers(), identity=lambda _: identity)

    def test_nested_repository_cannot_inherit_product_by_path_alone(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            profiles.select_layers(self.nested, self.layers(), identity=lambda _: (self.nested, self.origin))

    def test_missing_dependency_fails_instead_of_silently_omitting(self):
        self.catalog["layers"][1]["scope"]["path"] = str(self.outside)
        with self.assertRaisesRegex(ValueError, "Missing required"):
            self.select(self.repo)

    def test_invalid_catalogs_are_rejected(self):
        variants = []
        for version in (True, 2):
            value = copy.deepcopy(self.catalog)
            value["schemaVersion"] = version
            variants.append(value)
        value = copy.deepcopy(self.catalog)
        value["layers"][0]["scope"]["extra"] = True
        variants.append(value)
        value = copy.deepcopy(self.catalog)
        value["layers"][1]["requires"] = ["product"]
        variants.append(value)
        value = copy.deepcopy(self.catalog)
        value["layers"][1]["id"] = "personal"
        variants.append(value)
        value = copy.deepcopy(self.catalog)
        value["layers"][1]["scope"]["path"] = "relative"
        variants.append(value)
        value = copy.deepcopy(self.catalog)
        value["layers"][2]["scope"]["origin"] = "https://user:example@example.invalid/repo"
        variants.append(value)
        for origin in ("https://example@example.invalid/repo", "https://example.invalid/repo?token=example"):
            value = copy.deepcopy(self.catalog)
            value["layers"][2]["scope"]["origin"] = origin
            variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                profiles.parse_catalog(value, self.home)

    def test_duplicate_json_keys_are_rejected(self):
        path = self.home / "catalog.json"
        path.write_text('{"schemaVersion":1,"schemaVersion":1,"layers":[]}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            profiles.load_catalog(path)

    def test_missing_catalog_and_workspace_do_not_fall_back(self):
        with self.assertRaisesRegex(ValueError, "catalog missing"):
            profiles.load_catalog(self.home / "missing.json")
        with self.assertRaisesRegex(ValueError, "existing directory"):
            self.select(self.home / "missing")

    def test_preview_reports_selection_without_claiming_installation(self):
        with (
            patch.object(profiles, "load_catalog", return_value=self.layers()),
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            selected = profiles.show_plan(self.outside)
        self.assertEqual([layer.id for layer in selected], ["personal"])
        self.assertIn("installerer eller verifiserer ikke", output.getvalue())

    def test_repository_metadata_lookup_clears_git_environment(self):
        replies = [
            subprocess.CompletedProcess([], 0, str(self.repo) + "\n"),
            subprocess.CompletedProcess([], 0, self.origin + "\n"),
        ]
        with (
            patch.dict(os.environ, {"GIT_DIR": "poison", "GIT_CONFIG_COUNT": "1"}),
            patch.object(profiles.subprocess, "run", side_effect=replies) as run,
        ):
            self.assertEqual(profiles.repository_identity(self.nested), (self.repo, self.origin))
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertNotIn("GIT_DIR", call.kwargs["env"])
            self.assertNotIn("GIT_CONFIG_COUNT", call.kwargs["env"])
            self.assertNotIn("fetch", call.args[0])

    def test_real_git_identity_lookup_is_read_only(self):
        def git(*args):
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
            subprocess.run(
                ["git", "-c", "init.templateDir=", "-C", str(self.repo), *args],
                env=env, check=True, capture_output=True,
            )
        git("init", "--initial-branch=main")
        git("remote", "add", "origin", self.origin)
        before = {str(path.relative_to(self.repo)): path.read_bytes()
                  for path in self.repo.rglob("*") if path.is_file()}
        self.assertEqual(profiles.repository_identity(self.nested), (self.repo, self.origin))
        after = {str(path.relative_to(self.repo)): path.read_bytes()
                 for path in self.repo.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
