"""Create initial trial accounts once; never reset existing account passwords."""
import json
import os
import secrets
from pathlib import Path

from sqlalchemy import select

from patient_follow_up_system.auth import hash_password
from patient_follow_up_system.database import SessionLocal
from patient_follow_up_system.models import User, UserRole

accounts = []
with SessionLocal() as db:
    for username, display_name, role in [
        ("trial_admin", "试用管理员", UserRole.ADMIN),
        ("trial_doctor", "试用医生", UserRole.DOCTOR),
    ]:
        if db.scalar(select(User).where(User.username == username)):
            continue
        password = secrets.token_urlsafe(18)
        db.add(User(username=username, display_name=display_name, role=role,
                    password_hash=hash_password(password), is_active=True))
        accounts.append({"username": username, "password": password, "role": role.value})
    db.commit()
if accounts:
    path = Path("/etc/patientfollowup/initial-accounts.json")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(accounts, output, ensure_ascii=False, indent=2)
print("Initial account bootstrap finished; passwords were not printed.")
