import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from patient_follow_up_system.auth import hash_password  # noqa: E402
from patient_follow_up_system.database import SessionLocal  # noqa: E402
from patient_follow_up_system.models import User, UserRole  # noqa: E402


DEMO_USERS = (
    ("demo_admin", "虚构管理员（演示）", UserRole.ADMIN),
    ("demo_doctor", "虚构医生（演示）", UserRole.DOCTOR),
    ("demo_patient", "虚构患者（演示）", UserRole.PATIENT),
)


def read_password(username: str) -> str:
    password = getpass(f"请输入 {username} 的演示密码（至少 12 个字符，不会回显）: ")
    if len(password) < 12:
        raise ValueError(f"{username} 的演示密码少于 12 个字符")

    confirmation = getpass(f"请再次输入 {username} 的演示密码: ")
    if password != confirmation:
        raise ValueError(f"{username} 的两次密码输入不一致")
    return password


def main() -> None:
    with SessionLocal() as session:
        existing_usernames = set(
            session.scalars(
                select(User.username).where(
                    User.username.in_(username for username, _, _ in DEMO_USERS)
                )
            )
        )
        missing_users = [
            demo_user
            for demo_user in DEMO_USERS
            if demo_user[0] not in existing_usernames
        ]

        if not missing_users:
            print("DEMO_USERS_ALREADY_EXIST=True")
            return

        passwords = {
            username: read_password(username)
            for username, _, _ in missing_users
        }

        for username, display_name, role in missing_users:
            session.add(
                User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(passwords[username]),
                    role=role,
                    is_active=True,
                )
            )

        session.commit()

        for username, display_name, role in missing_users:
            print(f"CREATED={username},{role.value},{display_name}")
        print(f"DEMO_USERS_CREATED={len(missing_users)}")


if __name__ == "__main__":
    main()
