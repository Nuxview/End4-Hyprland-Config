"""Exercise the utility in an isolated repo and config directory."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "reapply-custom-configs"


class ReapplyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        shutil.copy2(SCRIPT, self.repo / SCRIPT.name)
        self.config = self.root / "config"
        self.config.mkdir()
        self.state = self.root / "state"
        self.data = self.root / "data"
        self.data.mkdir()
        self.env = dict(os.environ, XDG_CONFIG_HOME=str(self.config), XDG_DATA_HOME=str(self.data), XDG_STATE_HOME=str(self.state))
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.base = "header\n" + "unchanged\n" * 10 + "    old\nfooter\n"
        self.custom = self.base.replace("old", "fixed")
        source = self.repo / "dots/.config"
        source.mkdir(parents=True)
        for name in ("one.qml", "two.qml"):
            (source / name).write_text(self.base)
            (self.config / name).write_text(self.base)
        self.git("add", ".")
        self.git("commit", "-qm", "Base")
        self.git("checkout", "-qb", "custom-changes")
        for name in ("one.qml", "two.qml"):
            (source / name).write_text(self.custom)
        self.git("commit", "-qam", "Custom fixes")
        self.git("update-ref", "refs/remotes/origin/custom-changes", "HEAD")
        self.git("checkout", "main")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL)

    def run_utility(self, *args):
        return subprocess.run([str(self.repo / SCRIPT.name), *args], env=self.env, capture_output=True, text=True)

    def test_apply_backup_repeat_and_preserve_update(self):
        updated = self.base.replace("header", "upstream header")
        (self.config / "one.qml").write_text(updated)
        result = self.run_utility()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.config / "one.qml").read_text(), updated.replace("old", "fixed"))
        self.assertEqual((self.config / "two.qml").read_text(), self.custom)
        backups = list((self.state / "reapply-custom-configs").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".config/one.qml").read_text(), updated)
        result = self.run_utility()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Already applied"), 2)
        self.assertEqual(len(list((self.state / "reapply-custom-configs").iterdir())), 1)

    def test_dry_run(self):
        result = self.run_utility("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Would apply"), 2)
        self.assertEqual((self.config / "one.qml").read_text(), self.base)
        self.assertFalse(self.state.exists())

    def test_conflict_changes_nothing(self):
        conflict = self.base.replace("old", "conflicting upstream fix")
        (self.config / "two.qml").write_text(conflict)
        result = self.run_utility()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.config / "one.qml").read_text(), self.base)
        self.assertEqual((self.config / "two.qml").read_text(), conflict)
        self.assertFalse(self.state.exists())

    def test_missing_file_changes_nothing(self):
        (self.config / "two.qml").unlink()
        self.assertNotEqual(self.run_utility().returncode, 0)
        self.assertEqual((self.config / "one.qml").read_text(), self.base)
        self.assertFalse(self.state.exists())

    def test_existing_fix_with_different_indentation_and_symlink(self):
        (self.config / "one.qml").write_text(self.custom.replace("    fixed", "        fixed"))
        target = self.root / "linked.qml"
        (self.config / "two.qml").rename(target)
        (self.config / "two.qml").symlink_to(target)
        result = self.run_utility()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Already applied: one.qml", result.stdout)
        self.assertTrue((self.config / "two.qml").is_symlink())
        self.assertEqual(target.read_text(), self.custom)

    def test_missing_branch(self):
        self.assertNotEqual(self.run_utility("--ref", "missing").returncode, 0)
        self.assertEqual((self.config / "one.qml").read_text(), self.base)
        self.assertFalse(self.state.exists())

    def test_discovers_future_files_and_shared_data(self):
        self.git("checkout", "custom-changes")
        for name in ("dots/.config/extra.qml", "dots/.local/share/icons/icon.svg"):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.base)
        self.git("add", ".")
        self.git("commit", "-qm", "Additional base files")
        self.git("branch", "-f", "main", "HEAD")
        for name in ("dots/.config/extra.qml", "dots/.local/share/icons/icon.svg"):
            (self.repo / name).write_text(self.custom)
        self.git("commit", "-qam", "More customizations")
        self.git("update-ref", "refs/remotes/origin/custom-changes", "HEAD")
        (self.config / "extra.qml").write_text(self.base)
        (self.data / "icons").mkdir()
        (self.data / "icons/icon.svg").write_text(self.base)
        result = self.run_utility()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.config / "extra.qml").read_text(), self.custom)
        self.assertEqual((self.data / "icons/icon.svg").read_text(), self.custom)
        backup = next((self.state / "reapply-custom-configs").iterdir())
        self.assertEqual((backup / ".local/share/icons/icon.svg").read_text(), self.base)

    def test_added_source_file_changes_nothing(self):
        self.git("checkout", "custom-changes")
        (self.repo / "dots/.config/new.qml").write_text("new\n")
        self.git("add", ".")
        self.git("commit", "-qm", "New file")
        self.git("update-ref", "refs/remotes/origin/custom-changes", "HEAD")
        self.assertNotEqual(self.run_utility().returncode, 0)
        self.assertEqual((self.config / "one.qml").read_text(), self.base)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
