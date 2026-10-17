"""Клиент для нового протокола: python3 bank_client.py alice."""
from pathlib import Path
import secrets
import socket
import sys


class BankClient:
    def __init__(self, host="127.0.0.1", port=9999):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.stream = self.sock.makefile("rb")
        if self.stream.readline() != b"BANK SERVER READY\n":
            self.close()
            raise ConnectionError("Server unavailable")

    def cmd(self, line):
        if "\n" in line or "\r" in line:
            raise ValueError("One command per line")
        self.sock.sendall((line + "\n").encode())
        reply = self.stream.readline()
        if not reply:
            raise ConnectionError("Connection closed")
        return reply.decode().strip()

    def transfer(self, to_id, amount, comment="", request_id=None):
        nonce = self.cmd("NONCE")
        if not nonce.startswith("OK|"):
            return nonce
        request_id = request_id or secrets.token_hex(16)
        return self.cmd(f"TRANSFER {to_id} {amount} {request_id} {nonce[3:]} {comment}".rstrip())

    def close(self):
        if hasattr(self, "stream"):
            self.stream.close()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    login = sys.argv[1] if len(sys.argv) > 1 else "alice"
    if login not in {"admin", "alice", "bob"}:
        raise SystemExit("Выберите admin, alice или bob")
    password = (Path(__file__).resolve().parent / ".secrets" / (login + "_password")).read_text().strip()
    # На каждую команду новое соединение: пауза пользователя не нарушает таймаут сервера.
    while True:
        command = input("Команда (BALANCE, HISTORY, TRANSFER 3 10.00, QUIT): ").strip()
        if command.upper() == "QUIT":
            break
        with BankClient() as client:
            reply = client.cmd(f"LOGIN {login} {password}")
            if not reply.startswith("OK|"):
                print(reply)
                continue
            if command.upper().startswith("TRANSFER "):
                fields = command.split(" ", 3)
                if len(fields) < 3:
                    print("TRANSFER <id> <сумма> [комментарий]")
                    continue
                print(client.transfer(fields[1], fields[2], fields[3] if len(fields) == 4 else ""))
            else:
                print(client.cmd(command))
