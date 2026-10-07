import json
import logging
from pathlib import Path
import math
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8000

logging.basicConfig(
    filename=Path(__file__).with_name("server.log"),
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("server")


USERS_DATA = {
    "user1": {"name": "Алексей", "game": "Dota 2", "level": 42, "score": 15320, "playtime_hours": 210},
    "user2": {"name": "Мария", "game": "Valorant", "level": 30, "score": 9870, "playtime_hours": 95},
    "user3": {"name": "Игорь", "game": "CS2", "level": 55, "score": 21000, "playtime_hours": 340},
}

class GameStatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(format, *args)
        super().log_message(format, *args)

    def setup(self):
        super().setup()

        self.connection.settimeout(5)

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (ConnectionError, TimeoutError):
            logger.warning("%s %s: клиент отключился до получения ответа", self.command, self.path)
            self.log_message("Клиент отключился до получения ответа")
        else:
            level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            logger.log(level, "%s %s -> %s; ответ: %s", self.command, self.path, status, body.decode("utf-8"))

    def error(self, status, message):
        self.send_json(status, {"error": message})

    def send_error(self, code, message=None, explain=None):

        if code == 501:
            self.error(405, "метод не поддерживается")
        else:
            self.error(code, message or "некорректный запрос")

    def do_GET(self):
        parts = self.path.split("/")
        if parts == ["", "users"]:
            self.send_json(200, USERS_DATA)
        elif len(parts) == 3 and parts[:2] == ["", "users"] and parts[2]:
            user = USERS_DATA.get(parts[2])
            if user is None:
                self.error(404, "Пользователь не найден")
            else:
                self.send_json(200, user)
        elif len(parts) == 4 and parts[:2] == ["", "users"] and parts[2] and parts[3] == "score":
            self.error(405, "метод не поддерживается")
        else:
            self.error(404, "маршрут не найден")

    def do_POST(self):
        parts = self.path.split("/")
        if parts == ["", "users"] or (len(parts) == 3 and parts[:2] == ["", "users"] and parts[2]):
            self.error(405, "метод не поддерживается")
            return
        if len(parts) != 4 or parts[:2] != ["", "users"] or not parts[2] or parts[3] != "score":
            self.error(404, "маршрут не найден")
            return
        user = USERS_DATA.get(parts[2])
        if user is None:
            self.error(404, "Пользователь не найден")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.error(400, "некорректный Content-Length")
            return
        if length <= 0 or self.headers.get("Transfer-Encoding"):
            self.error(400, "нужно JSON-тело с положительным Content-Length")
            return
        try:
            body = self.rfile.read(length)
        except (ConnectionError, TimeoutError):
            self.error(400, "тело запроса не получено полностью")
            return
        if len(body) != length:
            self.error(400, "тело запроса не получено полностью")
            return
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.error(400, "невалидный JSON")
            return
        if not isinstance(data, dict) or "score" not in data:
            self.error(400, "нужен объект с обязательным полем score")
            return
        score = data["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            self.error(400, "score должен быть числом")
            return
        if isinstance(score, float) and not math.isfinite(score):
            self.error(400, "score должен быть конечным числом")
            return
        try:
            total = user["score"] + score
        except OverflowError:
            self.error(400, "слишком большое значение score")
            return
        if isinstance(total, float) and not math.isfinite(total):
            self.error(400, "слишком большое значение score")
            return
        user["score"] = total
        self.send_json(200, user)


def run(host=HOST, port=PORT):
    with HTTPServer((host, port), GameStatsHandler) as server:
        logger.info("Сервер запущен на http://%s:%s", host, port)
        print(f"Сервер запущен на http://{host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nСервер остановлен.")
        finally:
            logger.info("Сервер остановлен")


if __name__ == "__main__":
    run()
