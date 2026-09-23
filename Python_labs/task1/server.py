
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8000

USERS_DATA = {
    "user1": {"name": "Алексей", "game": "Dota 2", "level": 42, "score": 15320, "playtime_hours": 210},
    "user2": {"name": "Мария", "game": "Valorant", "level": 30, "score": 9870, "playtime_hours": 95},
    "user3": {"name": "Игорь", "game": "CS2", "level": 55, "score": 21000, "playtime_hours": 340},
}

USER_ID_RE = re.compile(r"^/users/([^/]+)$")
USER_SCORE_RE = re.compile(r"^/users/([^/]+)/score$")


class GameStatsHandler(BaseHTTPRequestHandler):
    server_version = "GameStatsHTTP/1.0"

    # ---------- helpers ----------

    def _send_json(self, status: int, payload: dict) -> None:
        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # клиент оборвал соединение раньше, чем мы успели ответить —
            # это не сбой сервера, просто логируем и продолжаем работать
            self.log_message("клиент оборвал соединение до получения ответа")

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    # ---------- routes ----------

    def do_GET(self):
        try:
            if self.path == "/users":
                self._send_json(200, USERS_DATA)
                return

            match = USER_ID_RE.match(self.path)
            if match:
                user = USERS_DATA.get(match.group(1))
                if user is None:
                    self._error(404, "Пользователь не найден")
                else:
                    self._send_json(200, user)
                return

            self._error(404, "маршрут не найден")
        except Exception as exc:  # сервер не должен падать ни при каких условиях
            self.log_message("необработанная ошибка в GET: %s", exc)
            self._error(500, "внутренняя ошибка сервера")

    def do_POST(self):
        try:
            match = USER_SCORE_RE.match(self.path)
            if not match:
                self._error(404, "маршрут не найден")
                return

            user = USERS_DATA.get(match.group(1))
            if user is None:
                self._error(404, "Пользователь не найден")
                return

            length = int(self.headers.get("Content-Length", 0) or 0)
            raw_body = self.rfile.read(length) if length > 0 else b""

            try:
                data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._error(400, "невалидный JSON")
                return

            if "score" not in data:
                self._error(400, "поле score обязательно")
                return

            score_delta = data["score"]
            if isinstance(score_delta, bool) or not isinstance(score_delta, (int, float)):
                self._error(400, "score должен быть числом")
                return

            user["score"] += score_delta
            self._send_json(200, user)
        except Exception as exc:
            self.log_message("необработанная ошибка в POST: %s", exc)
            self._error(500, "внутренняя ошибка сервера")

    def do_DELETE(self):
        self._error(405, "метод не поддерживается")

    def do_PUT(self):
        self._error(405, "метод не поддерживается")

    def do_PATCH(self):
        self._error(405, "метод не поддерживается")

    # компактный формат логов вместо стандартного access-log
    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args if args else fmt}")


def run(host: str = HOST, port: int = PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), GameStatsHandler)
    print(f"Сервер запущен на http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
