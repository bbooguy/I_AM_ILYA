"""Учебный TCP-сервер банка. Команды и запуск описаны в README.md."""
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError

LOG = logging.getLogger("bank")
MAX_LINE = 4096
READ_TIMEOUT = 5
MAX_CLIENTS = 32
MAX_PER_IP = 16


class TransferRequest(BaseModel):
    to_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    nonce: str = Field(pattern=r"^[a-f0-9]{64}$")
    comment: str = Field(default="", max_length=200)


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1,
                          maxmem=64 * 1024 * 1024, dklen=32)


class Bank:
    def __init__(self, path, passwords):
        self.hash_slots = threading.BoundedSemaphore(2)
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL,
                    salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','user')),
                    balance INTEGER NOT NULL CHECK(balance >= 0));
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    from_id INTEGER NOT NULL REFERENCES users(id),
                    to_id INTEGER NOT NULL REFERENCES users(id),
                    amount INTEGER NOT NULL CHECK(amount > 0), comment TEXT NOT NULL,
                    request_id TEXT NOT NULL, UNIQUE(from_id, request_id));
            """)
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                if not passwords or set(passwords) != {"admin", "alice", "bob"}:
                    raise ValueError("Нужны начальные пароли admin, alice, bob")
                for uid, login, role, balance in [(1, "admin", "admin", 100000000),
                                                  (2, "alice", "user", 500000),
                                                  (3, "bob", "user", 10000)]:
                    password = passwords[login]
                    if not 16 <= len(password) <= 128 or any(c.isspace() for c in password):
                        raise ValueError("Начальный пароль: 16–128 символов без пробелов")
                    salt = secrets.token_bytes(16)
                    db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                               (uid, login, salt, password_hash(password, salt), role, balance))
        os.chmod(self.path, 0o600)
        # Для неизвестного логина тоже выполняется scrypt.
        self.dummy_salt = secrets.token_bytes(16)
        self.dummy_hash = password_hash(secrets.token_urlsafe(24), self.dummy_salt)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def authenticate(self, login, password):
        with self.connect() as db:
            user = db.execute("SELECT * FROM users WHERE login=?", (login,)).fetchone()
        salt = user["salt"] if user else self.dummy_salt
        expected = user["password_hash"] if user else self.dummy_hash
        with self.hash_slots:
            valid = hmac.compare_digest(password_hash(password, salt), expected)
        return dict(user) if user and valid else None

    def balance(self, uid):
        with self.connect() as db:
            row = db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        return f"OK|{Decimal(row['balance']) / 100:.2f}"

    def transfer(self, uid, req):
        if uid == req.to_id:
            return "ERR|Self-transfer forbidden"
        cents = int(req.amount * 100)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM transactions WHERE from_id=? AND request_id=?",
                          (uid, req.request_id)).fetchone():
                return "ERR|Duplicate request"
            if not db.execute("SELECT 1 FROM users WHERE id=?", (req.to_id,)).fetchone():
                return "ERR|Recipient not found"
            updated = db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                                 (cents, uid, cents))
            if updated.rowcount != 1:
                return "ERR|Insufficient funds"
            db.execute("UPDATE users SET balance=balance+? WHERE id=?", (cents, req.to_id))
            cursor = db.execute("INSERT INTO transactions(from_id,to_id,amount,comment,request_id) "
                                "VALUES(?,?,?,?,?)", (uid, req.to_id, cents, req.comment, req.request_id))
            tx_id = cursor.lastrowid
        LOG.info("transfer user=%d recipient=%d tx=%d", uid, req.to_id, tx_id)
        return f"OK|Transfer completed|tx={tx_id}"

    def history(self, uid):
        with self.connect() as db:
            rows = db.execute("SELECT id,ts,from_id,to_id,amount,comment FROM transactions "
                              "WHERE from_id=? OR to_id=? ORDER BY id DESC LIMIT 100", (uid, uid)).fetchall()
        return "OK|" + json.dumps([dict(row) for row in rows], ensure_ascii=False)

    def admin(self, command):
        with self.connect() as db:
            if command == "USERS":
                rows = db.execute("SELECT id,login,role,balance FROM users ORDER BY id").fetchall()
                return "OK|" + json.dumps([dict(row) for row in rows])
            if command == "STATS":
                count = db.execute("SELECT count(*) FROM transactions").fetchone()[0]
                return f"OK|transactions={count}"
        return "ERR|Use ADMIN USERS or ADMIN STATS"


class LoginLimiter:
    """Не более пяти попыток в минуту по IP и по логину, включая новые соединения."""
    def __init__(self):
        self.lock = threading.Lock()
        self.attempts = {}

    def allow(self, ip, login):
        now = time.monotonic()
        with self.lock:
            self.attempts = {key: value for key, value in self.attempts.items() if now - value[0] < 60}
            keys = [("ip", ip), ("login", login)]
            if len(self.attempts) >= 1024 or any(self.attempts.get(k, (now, 0))[1] >= 5 for k in keys):
                return False
            for key in keys:
                start, count = self.attempts.get(key, (now, 0))
                self.attempts[key] = (start, count + 1)
        return True


class ProtocolError(Exception):
    pass


def read_line(conn, pending):
    deadline = time.monotonic() + READ_TIMEOUT
    while b"\n" not in pending:
        if len(pending) > MAX_LINE:
            raise ProtocolError("Command too long")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProtocolError("Read timeout")
        conn.settimeout(remaining)
        chunk = conn.recv(min(1024, MAX_LINE + 1 - len(pending)))
        if not chunk:
            return None, b""
        pending += chunk
    raw, pending = pending.split(b"\n", 1)
    if len(raw) > MAX_LINE:
        raise ProtocolError("Command too long")
    line = raw.decode("utf-8", errors="strict").rstrip("\r")
    if any(ord(c) < 32 or ord(c) == 127 for c in line):
        raise ProtocolError("Invalid characters")
    return line, pending


class Server:
    def __init__(self, bank, host="127.0.0.1", port=9999):
        self.bank = bank
        self.host, self.port = host, port
        self.limiter = LoginLimiter()
        self.lock = threading.Lock()
        self.clients = set()
        self.per_ip = {}
        self.stop = threading.Event()
        self.socket = None
        self.ready = threading.Event()

    def handle(self, conn, addr):
        user, nonce, pending = None, None, b""
        started, commands = time.monotonic(), 0
        try:
            conn.settimeout(READ_TIMEOUT)
            conn.sendall(b"BANK SERVER READY\n")
            while not self.stop.is_set():
                line, pending = read_line(conn, pending)
                if line is None:
                    break
                commands += 1
                if commands > 100 and commands / max(time.monotonic() - started, 1) > 20:
                    raise ProtocolError("Too many commands")
                cmd, _, arg = line.partition(" ")
                cmd = cmd.upper()
                reply = "ERR|Unknown command"
                if cmd == "QUIT":
                    conn.sendall(b"BYE\n")
                    break
                if cmd == "HELP":
                    reply = "OK|LOGIN BALANCE NONCE TRANSFER HISTORY ADMIN QUIT"
                elif cmd == "LOGIN":
                    user, nonce = None, None
                    parts = arg.split()
                    if len(parts) != 2 or not re.fullmatch(r"[a-zA-Z0-9_]{1,32}", parts[0]) or len(parts[1]) > 128:
                        reply = "ERR|Invalid login format"
                    elif not self.limiter.allow(addr[0], parts[0]):
                        reply = "ERR|Too many login attempts"
                    else:
                        user = self.bank.authenticate(*parts)
                        LOG.info("login success=%s ip=%s", bool(user), addr[0])
                        reply = f"OK|{user['login']}|role={user['role']}" if user else "FAIL|Invalid login or password"
                elif not user:
                    reply = "ERR|Login required"
                elif cmd == "BALANCE" and not arg:
                    reply = self.bank.balance(user["id"])
                elif cmd == "NONCE" and not arg:
                    nonce = secrets.token_hex(32)
                    reply = "OK|" + nonce
                elif cmd == "TRANSFER":
                    parts = arg.split(" ", 4)
                    try:
                        if len(parts) < 4:
                            raise ValueError("Missing fields")
                        req = TransferRequest(to_id=parts[0], amount=parts[1], request_id=parts[2],
                                              nonce=parts[3], comment=parts[4] if len(parts) == 5 else "")
                        if nonce is None or not hmac.compare_digest(nonce, req.nonce):
                            reply = "ERR|Invalid or used nonce"
                        else:
                            nonce = None
                            reply = self.bank.transfer(user["id"], req)
                    except (ValidationError, ValueError):
                        reply = "ERR|Invalid transfer fields"
                elif cmd == "HISTORY":
                    if arg and (not arg.isascii() or not arg.isdecimal() or len(arg) > 10):
                        reply = "ERR|Invalid user id"
                    else:
                        uid = int(arg) if arg else user["id"]
                        reply = self.bank.history(uid) if uid == user["id"] or user["role"] == "admin" else "ERR|Access denied"
                elif cmd == "ADMIN":
                    reply = self.bank.admin(arg) if user["role"] == "admin" else "ERR|Access denied"
                conn.settimeout(READ_TIMEOUT)
                conn.sendall((reply + "\n").encode())
        except (ProtocolError, UnicodeDecodeError, TimeoutError) as error:
            LOG.warning("protocol rejected ip=%s type=%s", addr[0], type(error).__name__)
            try:
                conn.sendall(b"ERR|Invalid or timed out command\n")
            except OSError:
                pass
        except OSError:
            LOG.info("connection closed ip=%s", addr[0])
        except sqlite3.Error:
            LOG.exception("database operation failed")
            try:
                conn.sendall(b"ERR|Storage unavailable\n")
            except OSError:
                pass
        finally:
            conn.close()
            with self.lock:
                self.clients.discard(conn)
                self.per_ip[addr[0]] -= 1
            LOG.info("disconnect ip=%s", addr[0])

    def shutdown(self):
        self.stop.set()
        with self.lock:
            for client in self.clients:
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            self.socket = srv
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            self.port = srv.getsockname()[1]
            srv.listen(MAX_CLIENTS)
            srv.settimeout(0.5)
            self.ready.set()
            LOG.info("listening host=%s port=%d", self.host, self.port)
            while not self.stop.is_set():
                try:
                    conn, addr = srv.accept()
                except TimeoutError:
                    continue
                with self.lock:
                    if len(self.clients) >= MAX_CLIENTS or self.per_ip.get(addr[0], 0) >= MAX_PER_IP:
                        conn.close()
                        continue
                    self.clients.add(conn)
                    self.per_ip[addr[0]] = self.per_ip.get(addr[0], 0) + 1
                threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()


def run_server():
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    secret_dir = Path(os.environ.get("BANK_SECRET_DIR", ".secrets"))
    passwords = {name: (secret_dir / (name + "_password")).read_text().strip()
                 for name in ("admin", "alice", "bob")}
    bank = Bank(os.environ.get("BANK_DB", "data/bank.sqlite3"), passwords)
    server = Server(bank, os.environ.get("BANK_HOST", "127.0.0.1"), int(os.environ.get("BANK_PORT", "9999")))
    signal.signal(signal.SIGTERM, lambda *_: server.shutdown())
    try:
        server.serve()
    except KeyboardInterrupt:
        server.shutdown()
        LOG.info("stopped")


if __name__ == "__main__":
    run_server()
