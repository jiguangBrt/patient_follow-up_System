"""Keep legacy business data and refuse dropping new tables after use."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_portal_additive_migration_and_populated_downgrade_guard(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "portal-migration.db"
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + path.as_posix(), "PYTHONPATH": str(root / "src"), "PYTHONIOENCODING": "utf-8"}

    def migrate(*args, success=True):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result

    migrate("upgrade", "f05b31d6a902")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO users(id,username,display_name,password_hash,role,is_active) VALUES(1,'fictional','fictional','unchanged','doctor',1)")
        db.execute("INSERT INTO patients(id,patient_code,display_name,responsible_doctor_id) VALUES(1,'P-FICTIONAL','fictional',1)")
        before = {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in ("users", "patients", "patient_intake_submissions", "patient_grants")}
    migrate("upgrade", "head")
    migrate("check")
    with sqlite3.connect(path) as db:
        assert before == {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in before}
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    migrate("downgrade", "f05b31d6a902")
    migrate("upgrade", "head")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO doctor_enrollment_links(doctor_id,nonce,token_digest) VALUES(1,'fictional-nonce','fictional-digest')")
    result = migrate("downgrade", "f05b31d6a902", success=False)
    assert "已有患者门户或病情档案数据" in result.stderr
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT nonce FROM doctor_enrollment_links").fetchone() == ("fictional-nonce",)
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("a91c4e8f602b",)
