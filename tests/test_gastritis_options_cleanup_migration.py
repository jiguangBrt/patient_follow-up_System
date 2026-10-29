"""Drop only the retired confirmation table; retain actual clinical reviews."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_options_cleanup_drops_table_and_preserves_all_other_business_data(tmp_path):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "options-cleanup.db"
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + database.as_posix(), "PYTHONPATH": str(root / "src"), "PYTHONIOENCODING": "utf-8"}

    def migrate(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    migrate("upgrade", "d62b4c8e901a")
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users(id,username,display_name,password_hash,role,is_active) VALUES(1,'fixture','fictional','unchanged','doctor',1)")
        db.execute("INSERT INTO patients(id,patient_code,display_name,responsible_doctor_id) VALUES(1,'P-FIXTURE','fictional',1)")
        db.executemany("INSERT INTO gastritis_option_confirmations(doctor_id,schema_version,note) VALUES(1,?,?)", [("v1", "old fixture"), ("v2", "new fixture")])
        db.execute("INSERT INTO gastritis_records(patient_id,version,recorded_on,payload,source,status,created_by_id,confirmed_by_id,confirmed_at) VALUES(1,1,'2026-01-01','{\"hp\":{\"infection\":\"unknown\"}}','staff','confirmed',1,1,'2026-01-02 01:00:00')")
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if r[0] not in ("alembic_version", "gastritis_option_confirmations")]
        before = {name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in tables}
    migrate("upgrade", "head")
    migrate("check")
    with sqlite3.connect(database) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%gastritis_option_confirmations%'").fetchall()
        assert before == {name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in tables}
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("e73c5d9f012b",)
    result = migrate("downgrade", "d62b4c8e901a")
    assert "cannot be restored" in result.stderr
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT * FROM gastritis_option_confirmations").fetchall() == []
        assert before == {name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in tables}
    migrate("upgrade", "head")
    migrate("check")
    with sqlite3.connect(database) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='gastritis_option_confirmations'").fetchall()
        assert before == {name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in tables}
