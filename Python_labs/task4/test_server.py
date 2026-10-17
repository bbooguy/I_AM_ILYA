"""Проверки защиты на временной базе и локальном порту, без массовых атак."""
import concurrent.futures
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from pydantic import ValidationError
import main
from bank_client import BankClient


class BankTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.passwords = {name: secrets.token_urlsafe(24) for name in ("admin", "alice", "bob")}
        self.path = Path(self.temp.name) / "bank.sqlite3"
        self.bank = main.Bank(self.path, self.passwords)
        self.server = main.Server(self.bank, port=0)
        self.thread = threading.Thread(target=self.server.serve)
        self.thread.start()
        self.assertTrue(self.server.ready.wait(5))
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.shutdown()
        self.thread.join(6)
        self.temp.cleanup()

    def client(self, login="alice"):
        c = BankClient(port=self.server.port)
        self.clients.append(c)
        self.assertTrue(c.cmd(f"LOGIN {login} {self.passwords[login]}").startswith("OK|"))
        return c

    def request(self, amount="1.00", **kw):
        fields = dict(to_id=3, amount=amount, request_id=secrets.token_hex(16), nonce=secrets.token_hex(32))
        fields.update(kw)
        return main.TransferRequest(**fields)

    def test_login_and_password_storage(self):
        self.assertIsNone(self.bank.authenticate("alice", "qwerty"))
        self.assertIsNotNone(self.bank.authenticate("alice", self.passwords["alice"]))
        with self.bank.connect() as db:
            rows = db.execute("SELECT salt,password_hash FROM users").fetchall()
        self.assertEqual(len({r['salt'] for r in rows}), 3)
        self.assertTrue(all(len(r['password_hash']) == 32 for r in rows))

    def test_sql_injection_and_admin(self):
        c = BankClient(port=self.server.port)
        self.clients.append(c)
        self.assertTrue(c.cmd("LOGIN ' OR '1'='1 x").startswith("ERR|"))
        self.assertEqual(c.cmd("BALANCE"), "ERR|Login required")
        user = self.client()
        self.assertEqual(user.cmd("ADMIN USERS"), "ERR|Access denied")
        admin = self.client("admin")
        self.assertTrue(admin.cmd("ADMIN SELECT * FROM users").startswith("ERR|"))
        data = admin.cmd("ADMIN USERS")
        self.assertNotIn("password_hash", data)
        self.assertNotIn('salt', data)

    def test_amount_validation_and_self_transfer(self):
        for amount in ["-1", "0", "NaN", "Infinity", "0.001", "999999999999999"]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.request(amount)
        c = self.client()
        self.assertEqual(c.transfer(2, "1.00"), "ERR|Self-transfer forbidden")
        self.assertEqual(c.cmd("BALANCE"), "OK|5000.00")

    def test_normal_transfer_and_replay(self):
        c = self.client()
        nonce = c.cmd("NONCE")[3:]
        rid = secrets.token_hex(16)
        line = f"TRANSFER 3 10.00 {rid} {nonce} test"
        self.assertTrue(c.cmd(line).startswith("OK|"))
        self.assertTrue(c.cmd(line).startswith("ERR|"))
        other = self.client()
        self.assertEqual(other.transfer(3, "10.00", request_id=rid), "ERR|Duplicate request")
        self.assertTrue(other.cmd(line).startswith("ERR|"))
        self.assertEqual(c.cmd("BALANCE"), "OK|4990.00")
        self.assertTrue(c.cmd("TRANSFER 3 1000 stolen").startswith("ERR|"))

    def test_idor(self):
        c = self.client()
        self.assertEqual(c.cmd("HISTORY 3"), "ERR|Access denied")
        self.assertEqual(c.cmd("HISTORY"), "OK|[]")
        self.assertTrue(c.cmd("HISTORY -1").startswith("ERR|"))

    def test_race_and_money_conservation(self):
        def transfer(_):
            return self.bank.transfer(2, self.request("400.00"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(transfer, range(20)))
        self.assertEqual(sum(r.startswith("OK|") for r in results), 12)
        self.assertEqual(self.bank.balance(2), "OK|200.00")
        self.assertEqual(self.bank.balance(3), "OK|4900.00")
        with self.bank.connect() as db:
            self.assertEqual(db.execute("SELECT sum(balance) FROM users").fetchone()[0], 100510000)
            self.assertEqual(db.execute("SELECT count(*) FROM transactions").fetchone()[0], 12)

    def test_bruteforce_across_connections(self):
        for i in range(6):
            with BankClient(port=self.server.port) as c:
                response = c.cmd(f"LOGIN alice wrong{i}")
            self.assertTrue(response.startswith("FAIL|" if i < 5 else "ERR|Too many"))

    def test_tcp_fragmentation_and_two_commands(self):
        c = self.client()
        c.sock.sendall(b"BAL")
        c.sock.sendall(b"ANCE\nHISTORY\n")
        self.assertEqual(c.stream.readline().decode().strip(), "OK|5000.00")
        self.assertEqual(c.stream.readline().decode().strip(), "OK|[]")

    def test_fuzz_invalid_and_oversized_input(self):
        c = self.client()
        for line in ["TRANSFER", "TRANSFER abc xyz", "HISTORY abc", "UNKNOWN"]:
            self.assertTrue(c.cmd(line).startswith("ERR|"))
        self.assertEqual(c.cmd("BALANCE"), "OK|5000.00")
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=3) as s:
            s.recv(64)
            s.sendall(b"x" * 4097)
            self.assertTrue(s.recv(128).startswith(b"ERR|"))

    def test_slow_incomplete_line_has_absolute_deadline(self):
        with patch.object(main, "READ_TIMEOUT", 0.4):
            with socket.create_connection(("127.0.0.1", self.server.port), timeout=3) as s:
                s.recv(64)
                s.sendall(b"LOGIN a")
                self.assertTrue(s.recv(128).startswith(b"ERR|"))

    def test_connection_limit(self):
        with patch.object(main, "MAX_PER_IP", 2):
            a = self.client()
            b = self.client("bob")
            with socket.create_connection(("127.0.0.1", self.server.port), timeout=3) as s:
                self.assertEqual(s.recv(64), b"")
            self.assertEqual(a.cmd("BALANCE"), "OK|5000.00")
            self.assertEqual(b.cmd("BALANCE"), "OK|100.00")

    def test_persistence_and_json_tampering(self):
        self.bank.transfer(2, self.request("1.00"))
        (Path(self.temp.name) / "bank_db.json").write_text(json.dumps({"balance": 999999999}))
        reopened = main.Bank(self.path, None)
        self.assertEqual(reopened.balance(2), "OK|4999.00")
        self.assertIsNotNone(reopened.authenticate("alice", self.passwords["alice"]))

    def test_logs_do_not_contain_password(self):
        with self.assertLogs("bank", level="INFO") as logs:
            self.client()
        self.assertNotIn(self.passwords['alice'], '\n'.join(logs.output))

    def test_failed_login_clears_session(self):
        c = self.client()
        self.assertTrue(c.cmd("LOGIN alice wrong").startswith("FAIL|"))
        self.assertEqual(c.cmd("BALANCE"), "ERR|Login required")

    def test_transaction_rolls_back_if_record_fails(self):
        with self.bank.connect() as db:
            db.execute("CREATE TRIGGER fail_record BEFORE INSERT ON transactions "
                       "BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.bank.transfer(2, self.request("10.00"))
        self.assertEqual(self.bank.balance(2), "OK|5000.00")
        self.assertEqual(self.bank.balance(3), "OK|100.00")

    def test_replay_id_survives_restart(self):
        req = self.request("1.00")
        self.bank.transfer(2, req)
        reopened = main.Bank(self.path, None)
        self.assertEqual(reopened.transfer(2, req), "ERR|Duplicate request")
        self.assertEqual(reopened.balance(2), "OK|4999.00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
