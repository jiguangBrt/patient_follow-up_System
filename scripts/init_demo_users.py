import os
import sys
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
# Local demo only. Never use this password outside an isolated development setup.
DEMO_PASSWORD = "123456"


def main() -> None:
    if os.getenv("APP_ENV", "development").lower() not in {"development", "local", "test"}:
        raise SystemExit("此脚本仅用于本地演示，不允许重置服务器账号。")
    with SessionLocal() as session:
        for username, display_name, role in DEMO_USERS:
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(username=username, display_name=display_name)
                session.add(user)

            user.display_name = display_name
            user.password_hash = hash_password(DEMO_PASSWORD)
            user.role = role
            user.is_active = True

        session.commit()

        print("演示账号已创建或重置：")
        for username, display_name, role in DEMO_USERS:
            print(f"  {username} ({role.value}) - {display_name}")
        print(f"统一演示密码：{DEMO_PASSWORD}")
        print("仅限本地演示使用，请勿用于云端或真实患者数据。")


if __name__ == "__main__":
    main()
