"""Verify upgrade against pre-team data and refuse a destructive downgrade."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_team_migration_preserves_accounts_and_checks_metadata(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "migration.db"
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + path.as_posix(),
        "PYTHONPATH": str(root / "src"),
        "PYTHONIOENCODING": "utf-8",
    }

    def alembic(*args, success=True):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0
        return result

    alembic("upgrade", "b72d9015f43a")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO users (id,username,display_name,password_hash,role,is_active) VALUES (1,'doctor','fictional','untouched-hash','doctor',1)"
        )
        db.execute(
            "INSERT INTO patients (id,patient_code,display_name,responsible_doctor_id) VALUES (1,'P-FIXTURE','fictional',1)"
        )
    alembic("upgrade", "head")
    alembic("check")
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT username,password_hash,role,mentor_doctor_id FROM users"
        ).fetchone() == ("doctor", "untouched-hash", "doctor", None)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    alembic("downgrade", "b72d9015f43a")
    alembic("upgrade", "head")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO users (id,username,display_name,password_hash,role,is_active,mentor_doctor_id) VALUES (2,'student','fixture','fixture','student',1,1)"
        )
    alembic("downgrade", "b72d9015f43a", success=False)
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT role,mentor_doctor_id FROM users WHERE id=2"
        ).fetchone() == ("student", 1)
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "c83e2a17d604"
        )
