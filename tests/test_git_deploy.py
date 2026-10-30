"""Run on Linux as root in isolated temporary repositories; never use real services."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(
    os.name == "posix" and getattr(os, "geteuid", lambda: -1)() == 0,
    "Linux/root deployment harness",
)
class GitDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="patientfollowup-git-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.root / "app"
        (self.base / "releases").mkdir(parents=True)
        self.origin = self.root / "origin.git"
        self.author = self.root / "author"
        self.git("init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.git("init", "--quiet", "--initial-branch=main", str(self.author))
        self.git("-C", str(self.author), "config", "user.name", "Fixture")
        self.git(
            "-C", str(self.author), "config", "user.email", "fixture@example.invalid"
        )
        self.git("-C", str(self.author), "remote", "add", "origin", str(self.origin))
        (self.author / "src").mkdir()
        (self.author / "src/app.py").write_text("value = 1\n")
        (self.author / "pyproject.toml").write_text("# fixture\n")
        (self.author / "uv.lock").write_text("# fixture lock\n")
        (self.author / ".gitignore").write_text(".venv/\n__pycache__/\n")
        self.old_commit = self.commit("initial")
        self.git(
            "clone",
            "--quiet",
            "--branch",
            "main",
            str(self.origin),
            str(self.base / "source"),
        )
        self.old = self.base / "releases/initial"
        self.git(
            "-C",
            str(self.base / "source"),
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(self.old),
            self.old_commit,
        )
        (self.base / "current").symlink_to(self.old, target_is_directory=True)
        self.fake_bin = self.root / "commands"
        self.fake_bin.mkdir()
        self.log = self.root / "commands.log"
        self.env = os.environ | {
            "PATH": str(self.fake_bin) + os.pathsep + os.environ["PATH"],
            "PATIENTFOLLOWUP_BASE": str(self.base),
            "PATIENTFOLLOWUP_ENV_FILE": str(self.root / "app.env"),
            "PATIENTFOLLOWUP_UV_BIN": str(self.root / "missing-uv"),
            "FIXTURE_BASE": str(self.base),
            "FIXTURE_LOG": str(self.log),
        }
        (self.root / "app.env").write_text("DATABASE_URL=sqlite:///fixture.db\n")
        self.executable(
            self.fake_bin / "systemctl",
            """import os,sys
with open(os.environ['FIXTURE_LOG'],'a') as f:f.write('systemctl '+ ' '.join(sys.argv[1:])+'\\n')
""",
        )
        self.executable(
            self.fake_bin / "runuser",
            """import os,sys
args=sys.argv[sys.argv.index('--')+1:]
os.execv(args[0],args)
""",
        )
        self.executable(
            self.fake_bin / "curl",
            """import os,sys
from pathlib import Path
current=(Path(os.environ['FIXTURE_BASE'])/'current').resolve()
sys.exit(1 if os.environ.get('FIXTURE_BAD_HEALTH') and current.name!='initial' else 0)
""",
        )
        self.executable(self.fake_bin / "sleep", "")
        venv = self.root / "venv"
        (venv / "bin").mkdir(parents=True)
        self.executable(
            venv / "bin/python",
            """import os,sys
with open(os.environ['FIXTURE_LOG'],'a') as f:f.write('python '+ ' '.join(sys.argv[1:3])+'\\n')
if sys.argv[1:]==['-m','alembic','current']:print('revision1 (head)')
if sys.argv[1:]==['-m','alembic','heads']:print(os.environ.get('FIXTURE_CODE_REVISION','revision1')+' (head)')
if sys.argv[1:]==['-m','alembic','upgrade','head'] and os.environ.get('FIXTURE_BAD_MIGRATION'):sys.exit(1)
""",
        )
        (self.old / ".venv").symlink_to(venv, target_is_directory=True)
        self.script = (
            Path(__file__).resolve().parents[1] / "deploy/linux/update-from-git.sh"
        )

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], stderr=subprocess.DEVNULL, text=True
        ).strip()

    def commit(self, text):
        self.git("-C", str(self.author), "add", ".")
        self.git("-C", str(self.author), "commit", "--quiet", "-m", text)
        self.git("-C", str(self.author), "push", "--quiet", "origin", "main")
        return self.git("-C", str(self.author), "rev-parse", "HEAD")

    def change(self):
        (self.author / "src/app.py").write_text("value = 2\n")
        return self.commit("next")

    @staticmethod
    def executable(path, body):
        path.write_text("#!/usr/bin/python3\n" + body)
        path.chmod(0o755)

    def update(self, *args):
        # Verify all service/network/process stubs exist before executing any update.
        self.assertTrue(
            all(
                (self.fake_bin / n).is_file()
                for n in ("systemctl", "curl", "runuser", "sleep")
            )
        )
        return subprocess.run(
            ["bash", str(self.script), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def assert_not_stopped(self):
        text = self.log.read_text() if self.log.exists() else ""
        self.assertNotIn("systemctl stop", text)

    def test_check_fetches_main_without_changing_running_release(self):
        target = self.change()
        result = self.update("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(target, result.stdout)
        self.assertEqual((self.base / "current").resolve(), self.old)
        self.assert_not_stopped()

    def test_update_switches_exact_commit_and_second_run_is_a_noop(self):
        target = self.change()
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stderr)
        current = (self.base / "current").resolve()
        self.assertEqual(self.git("-C", str(current), "rev-parse", "HEAD"), target)
        self.assertEqual(self.git("-C", str(current), "status", "--porcelain"), "")
        log = self.log.read_text()
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no restart", result.stdout)
        self.assertEqual(self.log.read_text(), log)

    def test_dirty_source_is_not_overwritten(self):
        self.change()
        (self.base / "source/src/app.py").write_text("local_source_change = True\n")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        self.assert_not_stopped()

    def test_fetch_failure_does_not_stop_running_app(self):
        self.git(
            "-C",
            str(self.base / "source"),
            "remote",
            "set-url",
            "origin",
            str(self.root / "missing-origin.git"),
        )
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot fetch main", result.stderr)
        self.assertEqual((self.base / "current").resolve(), self.old)
        self.assert_not_stopped()

    def test_dirty_running_release_is_not_overwritten(self):
        self.change()
        (self.old / "src/app.py").write_text("local_running_change = True\n")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        self.assert_not_stopped()

    def test_failed_health_check_restores_previous_code(self):
        self.change()
        self.env["FIXTURE_BAD_HEALTH"] = "1"
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.base / "current").resolve(), self.old)
        self.assertIn("restoring previous", result.stderr)
        self.assertGreaterEqual(self.log.read_text().count("systemctl start"), 2)

    def test_failed_migration_keeps_previous_release_and_restarts_it(self):
        self.change()
        self.env.update(FIXTURE_BAD_MIGRATION="1", FIXTURE_CODE_REVISION="revision2")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.base / "current").resolve(), self.old)
        self.assertIn("systemctl start", self.log.read_text())
        self.assertIn("backup.py", self.log.read_text())

    def test_unprepared_dependencies_do_not_stop_running_app(self):
        (self.author / "uv.lock").write_text("# changed dependencies\n")
        self.commit("dependency update")
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uv is required", result.stderr)
        self.assertEqual((self.base / "current").resolve(), self.old)
        self.assert_not_stopped()


if __name__ == "__main__":
    unittest.main(verbosity=2)
