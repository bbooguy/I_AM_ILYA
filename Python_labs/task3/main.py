#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import socket
import hashlib
import threading
from decimal import Decimal
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ValidationError


HOST = "127.0.0.1"
PORT = 9999
DB_FILE = "bank_db.json"


class User(BaseModel):
    id: int
    login: str
    password_hash: str
    role: Literal["admin", "user"] = "user"
    balance: Decimal = Decimal("0")


class Transaction(BaseModel):
    id: int
    ts: datetime
    from_id: int
    to_id: int
    amount: Decimal
    comment: str = ""


class LoginRequest(BaseModel):
    login: str
    password: str


class TransferRequest(BaseModel):
    to_id: int
    amount: Decimal
    comment: str = ""

db = {
    "users": [
        User(id=1, login="admin", role="admin",
             password_hash=hashlib.md5(b"admin123").hexdigest(),
             balance=Decimal("1000000")),
        User(id=2, login="alice", role="user",
             password_hash=hashlib.md5(b"qwerty").hexdigest(),
             balance=Decimal("5000")),
        User(id=3, login="bob", role="user",
             password_hash=hashlib.md5(b"12345").hexdigest(),
             balance=Decimal("100")),
    ],
    "transactions": [],
    "next_tx_id": 1,
}


def save_db():
    data = {
        "users": [u.model_dump(mode="json") for u in db["users"]],
        "transactions": [t.model_dump(mode="json") for t in db["transactions"]],
        "next_tx_id": db["next_tx_id"],
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_db():
    global db
    if not os.path.exists(DB_FILE):
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        db["users"] = [User(**u) for u in raw["users"]]
        db["transactions"] = [Transaction(**t) for t in raw["transactions"]]
        db["next_tx_id"] = raw.get("next_tx_id", 1)
        print(f"[DB] Loaded {len(db['users'])} users, "
              f"{len(db['transactions'])} transactions")
    except Exception as e:
        print(f"[!] Failed to load DB: {e}")


def fake_sql(query: str):
    print(f"[SQL] {query}")
    if "FROM users" not in query:
        return []

    where_part = query.split("WHERE", 1)[-1] if "WHERE" in query else ""
    compact = where_part.replace(" ", "").replace("\t", "")

    if "'1'='1" in compact or '"1"="1"' in compact or "1=1" in compact:
        print("[SQL] !!! Tautology — returning ALL rows (authentication bypass)")
        return list(db["users"])

    matched = []
    for u in db["users"]:
        if f"'{u.login}'" in where_part and f"'{u.password_hash}'" in where_part:
            matched.append(u)
        elif f"id='{u.id}'" in where_part:
            matched.append(u)
        elif f"login='{u.login}'" in where_part and "password_hash" not in where_part:
            matched.append(u)
    return matched


def find_user_by_id(uid: int) -> Optional[User]:
    for u in db["users"]:
        if u.id == uid:
            return u
    return None


def record_tx(from_id: int, to_id: int, amount: Decimal, comment: str) -> Transaction:
    tx = Transaction(
        id=db["next_tx_id"],
        ts=datetime.now(),
        from_id=from_id,
        to_id=to_id,
        amount=amount,
        comment=comment,
    )
    db["transactions"].append(tx)
    db["next_tx_id"] += 1
    return tx


def do_transfer(sender: User, req: TransferRequest) -> str:
    receiver = find_user_by_id(req.to_id)
    if not receiver:
        return "ERR|Recipient not found"

    balance_before = sender.balance
    time.sleep(0.05)
    if balance_before < req.amount:
        return "ERR|Insufficient funds"

    sender.balance -= req.amount
    receiver.balance += req.amount
    tx = record_tx(sender.id, req.to_id, req.amount, req.comment)
    save_db()
    return f"OK|Transfer completed|tx={tx.id}|balance={sender.balance}"


def get_history(uid: int) -> str:
    rows = [t for t in db["transactions"] if t.from_id == uid or t.to_id == uid]
    return "OK|" + json.dumps([t.model_dump(mode="json") for t in rows],
                              ensure_ascii=False)


HELP = (
    "Commands:\n"
    "  LOGIN <login> <password>       — log in\n"
    "  BALANCE                        — current balance\n"
    "  TRANSFER <to_id> <amount> [c]  — transfer\n"
    "  HISTORY [uid]                  — transaction history\n"
    "  ADMIN <sql>                    — admin query\n"
    "  QUIT                           — exit\n"
)


def handle_client(conn: socket.socket, addr):
    print(f"[+] Connection: {addr}")
    current_user: Optional[User] = None
    try:
        conn.sendall(b"BANK SERVER READY\n")
        conn.sendall(b"LOGIN <login> <password>\n")

        while True:
            raw = conn.recv(4096)
            if not raw:
                break
            line = raw.decode(errors="ignore").strip()
            if not line:
                continue
            print(f"[{addr}] {line}")

            parts = line.split(" ", 1)
            cmd = parts[0].upper()
            arg = parts[1] if len(parts) > 1 else ""
            reply = "ERR|Unknown command (HELP for reference)"

            if cmd == "HELP":
                reply = "OK|\n" + HELP

            elif cmd == "LOGIN":
                try:
                    login_str, pwd_str = arg.split(" ", 1)
                    req = LoginRequest(login=login_str, password=pwd_str)
                except ValueError:
                    reply = "ERR|Format: LOGIN <login> <password>"
                except ValidationError as e:
                    reply = f"ERR|{e.errors()[0]['msg']}"
                else:
                    pwd_hash = hashlib.md5(req.password.encode()).hexdigest()
                    query = (f"SELECT * FROM users WHERE login = '{req.login}' "
                             f"AND password_hash = '{pwd_hash}'")
                    rows = fake_sql(query)
                    if rows:
                        current_user = rows[0]
                        reply = f"OK|{current_user.login}|role={current_user.role}"
                    else:
                        reply = "FAIL|Invalid login or password"

            elif cmd == "BALANCE":
                if not current_user:
                    reply = "ERR|Login required"
                else:
                    reply = f"OK|{current_user.balance}"

            elif cmd == "TRANSFER":
                if not current_user:
                    reply = "ERR|Login required"
                else:
                    try:
                        chunks = arg.split(" ", 2)
                        req = TransferRequest(
                            to_id=chunks[0],
                            amount=chunks[1],
                            comment=chunks[2] if len(chunks) > 2 else "",
                        )
                    except (IndexError, ValidationError) as e:
                        reply = f"ERR|{e}"
                    else:
                        reply = do_transfer(current_user, req)

            elif cmd == "HISTORY":
                if not current_user:
                    reply = "ERR|Login required"
                else:
                    if arg.strip():
                        try:
                            uid = int(arg)
                        except ValueError:
                            conn.sendall("ERR|uid must be a number\n".encode("utf-8"))
                            continue
                    else:
                        uid = current_user.id
                    reply = get_history(uid)

            elif cmd == "ADMIN":
                if not current_user or current_user.role != "admin":
                    reply = "ERR|Access denied"
                else:
                    rows = fake_sql(arg)
                    out = [u.model_dump(mode="json") for u in rows]
                    reply = "OK|" + json.dumps(out, ensure_ascii=False)

            elif cmd == "QUIT":
                conn.sendall(b"BYE\n")
                break

            conn.sendall((reply + "\n").encode())

    except Exception as e:
        print(f"[!] Error {addr}: {e}")
    finally:
        conn.close()
        print(f"[-] Disconnection: {addr}")


def run_server():
    load_db()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)

    print(f"[*] Banking server listening on {HOST}:{PORT}")
    print(f"[*] Storage: {os.path.abspath(DB_FILE)}")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr),
                             daemon=True).start()
    except KeyboardInterrupt:
        print("\n[*] Stopped")
    finally:
        srv.close()


if __name__ == "__main__":
    run_server()
