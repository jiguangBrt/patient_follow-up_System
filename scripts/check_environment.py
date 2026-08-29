import sys


def main() -> None:
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Python executable: {sys.executable}")
    print("Environment check passed.")


if __name__ == "__main__":
    main()
