import secrets
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def main() -> None:
    if not ENV_PATH.exists():
        raise RuntimeError("Local .env file does not exist")

    content = ENV_PATH.read_text(encoding="utf-8-sig")
    existing_keys = {
        line.split("=", 1)[0].strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }

    additions: list[str] = []
    if "AUTH_SECRET_KEY" not in existing_keys:
        additions.append(f"AUTH_SECRET_KEY={secrets.token_hex(32)}")
    if "ACCESS_TOKEN_EXPIRE_MINUTES" not in existing_keys:
        additions.append("ACCESS_TOKEN_EXPIRE_MINUTES=30")

    if additions:
        updated = content.rstrip() + "\n\n" + "\n".join(additions) + "\n"
        ENV_PATH.write_text(updated, encoding="utf-8")
        print("AUTH_CONFIG_CREATED=True")
    else:
        print("AUTH_CONFIG_EXISTS=True")


if __name__ == "__main__":
    main()
