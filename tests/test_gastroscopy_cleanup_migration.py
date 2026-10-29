"""Retiring one section deletes it from every version, preserving all other data."""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_cleanup_removes_only_top_level_section_from_all_history(tmp_path):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "cleanup.db"
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + database.as_posix(), "PYTHONPATH": str(root / "src"), "PYTHONIOENCODING": "utf-8"}

    def migrate(*args):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    migrate("upgrade", "a91c4e8f602b")
    fixtures = [
        {"gastroscopy": {"intestinal_metaplasia": "有", "source": "虚构旧报告"}, "symptoms": {"nausea": {"presence": "yes", "grade": 2}}, "basic": {"name": "虚构甲"}},
        {"gastroscopy": None, "hp": {"infection": "无"}, "diagnoses": [{"date": "2026-01-01", "name": "虚构名称", "source": "虚构原件"}]},
        {"hp": {"infection": "未知/待确认"}, "other_symptoms": "保留中文", "nested": {"gastroscopy": "仅清顶层，保留嵌套值"}},
    ]
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO users(id,username,display_name,password_hash,role,is_active) VALUES(1,'fixture','fictional','unchanged','doctor',1)")
        db.executemany("INSERT INTO patients(id,patient_code,display_name,responsible_doctor_id) VALUES(?,?,?,1)", [(1, "P-1", "虚构甲"), (2, "P-2", "虚构乙")])
        for i, payload in enumerate(fixtures, 1):
            db.execute("INSERT INTO gastritis_records(id,patient_id,version,recorded_on,payload,source,status,created_by_id,confirmed_by_id,confirmed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (i, 1 if i < 3 else 2, i if i < 3 else 1, "2026-01-01", json.dumps(payload, ensure_ascii=False), "patient" if i == 1 else "staff", "confirmed" if i == 2 else "draft", None if i == 1 else 1, 1 if i == 2 else None, "2026-01-02 01:00:00" if i == 2 else None, "2026-01-01 01:00:00"))
        before_records = db.execute("SELECT * FROM gastritis_records ORDER BY id").fetchall()
        other_tables = {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in ("users", "patients", "portal_access", "patient_documents", "gastritis_option_confirmations")}
    migrate("upgrade", "d62b4c8e901a")
    with sqlite3.connect(database) as db:
        after_records = db.execute("SELECT * FROM gastritis_records ORDER BY id").fetchall()
        columns = [row[1] for row in db.execute("PRAGMA table_info(gastritis_records)")]
        payload_index = columns.index("payload")
        assert len(after_records) == len(before_records)
        for before, after, fixture in zip(before_records, after_records, fixtures, strict=True):
            assert before[:payload_index] + before[payload_index + 1:] == after[:payload_index] + after[payload_index + 1:]
            assert json.loads(after[payload_index]) == {key: value for key, value in fixture.items() if key != "gastroscopy"}
            if "gastroscopy" not in fixture:
                assert before == after  # No rewrite at all for unaffected records.
        assert other_tables == {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in other_tables}
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("d62b4c8e901a",)
    result = migrate("downgrade", "a91c4e8f602b")
    assert "cannot be restored" in result.stderr
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT * FROM gastritis_records ORDER BY id").fetchall() == after_records
    migrate("upgrade", "d62b4c8e901a")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT * FROM gastritis_records ORDER BY id").fetchall() == after_records
