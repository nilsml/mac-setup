import importlib.util
from pathlib import Path
import shutil
import unittest


SBX = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_launcher", SBX / "install-launcher.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
RUNTIME = SBX / "tests" / ".runtime" / "launcher-install"


class LauncherInstallTest(unittest.TestCase):
    def setUp(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)
        import tempfile
        self.temp = tempfile.TemporaryDirectory(dir=RUNTIME)
        self.root = Path(self.temp.name)
        self.source = self.root / "repo" / "sbx"
        self.source.mkdir(parents=True)
        for name in launcher.FILES:
            if name.split("/")[0] in launcher.KITS:
                continue
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SBX / name, path)
        for name in launcher.KITS:
            shutil.copytree(SBX / name, self.source / name, symlinks=True)
        self.original_source, self.original_repo = launcher.SOURCE, launcher.REPOSITORY
        launcher.SOURCE, launcher.REPOSITORY = self.source, self.source.parent
        self.destination = self.root / "installed"

    def tearDown(self):
        launcher.SOURCE, launcher.REPOSITORY = self.original_source, self.original_repo
        self.temp.cleanup()

    def test_plan_and_install_are_complete(self):
        (self.source / "personal" / ".DS_Store").write_text("ignored")
        (self.source / "personal" / "private.txt").write_text("ignored")
        cache = self.source / "models" / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "private.pyc").write_text("ignored")
        plan = launcher.install(self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(plan, sorted(plan))
        self.assertEqual(plan, launcher.install(self.destination, apply=True))
        actual = sorted(p.relative_to(self.destination) for p in self.destination.rglob("*") if p.is_file())
        self.assertEqual(plan, actual)
        for name in launcher.FILES:
            self.assertIn(Path(name), plan)
        self.assertNotIn(Path("personal/private.txt"), plan)
        for path in plan:
            self.assertEqual((self.source / path).read_bytes(), (self.destination / path).read_bytes())

    def test_existing_nonempty_is_refused(self):
        self.destination.mkdir()
        (self.destination / "keep").write_text("untouched")
        with self.assertRaises(ValueError):
            launcher.install(self.destination, apply=True)
        self.assertEqual((self.destination / "keep").read_text(), "untouched")

    def test_unsafe_destinations_are_refused(self):
        for destination in (Path("/"), Path.home(), self.source, self.source.parent / "new"):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                launcher.install(destination)
        link = self.root / "link"
        link.symlink_to(self.root / "missing")
        with self.assertRaises(ValueError):
            launcher.install(link)

    def test_missing_and_symlink_sources_fail_before_writing(self):
        missing = self.source / launcher.FILES[0]
        missing.unlink()
        with self.assertRaises(ValueError):
            launcher.install(self.destination, apply=True)
        self.assertFalse(self.destination.exists())
        missing.symlink_to(SBX / launcher.FILES[0])
        with self.assertRaises(ValueError):
            launcher.install(self.destination, apply=True)
        self.assertFalse(self.destination.exists())
        missing.unlink()
        shutil.copy2(SBX / launcher.FILES[0], missing)
        kit_file = self.source / "personal" / "install.sh"
        kit_file.unlink()
        kit_file.symlink_to(SBX / "oc.py")
        with self.assertRaises(ValueError):
            launcher.install(self.destination, apply=True)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
