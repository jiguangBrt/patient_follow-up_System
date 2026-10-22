"""Back up SQLite consistently and include uploads; run as the application user."""
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

state = Path("/var/lib/patientfollowup")
backups = state / "backups"
backups.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
with tempfile.TemporaryDirectory() as temporary:
    snapshot = Path(temporary) / "app.db"
    with sqlite3.connect(f"file:{state}/app.db?mode=ro", uri=True) as source:
        with sqlite3.connect(snapshot) as target:
            source.backup(target)
    with tarfile.open(backups / f"patientfollowup-{stamp}.tar.gz", "w:gz") as archive:
        archive.add(snapshot, arcname="app.db")
        archive.add(state / "uploads", arcname="uploads")
print("Backup created:", stamp)
