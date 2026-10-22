import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("environment", ["production", "trial"])
def test_local_demo_reset_refuses_server_environments(tmp_path, environment):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "must-not-be-created.db"
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "init_demo_users.py")],
        cwd=root,
        env={**os.environ, "APP_ENV": environment, "DATABASE_URL": f"sqlite:///{database.as_posix()}", "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "仅用于本地演示" in result.stderr
    assert not database.exists()
