"""Создать случайные пароли для первого запуска. Существующие не заменяются."""
import os
from pathlib import Path
import secrets

if __name__ == "__main__":
    os.umask(0o077)
    folder = Path(__file__).resolve().parent / ".secrets"
    folder.mkdir(mode=0o700, exist_ok=True)
    for login in ("admin", "alice", "bob"):
        path = folder / (login + "_password")
        if not path.exists():
            with path.open("x") as stream:
                stream.write(secrets.token_urlsafe(24) + "\n")
        path.chmod(0o600)
    print("Пароли сохранены в .secrets/. Не добавляйте эту папку в Git.")
