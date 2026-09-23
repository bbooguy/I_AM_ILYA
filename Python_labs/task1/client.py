#!/usr/bin/env python3
"""
Интерактивный клиент для задания №1.

Запросы вводятся текстом в формате:
    МЕТОД ПУТЬ [ТЕЛО]
Например:
    GET /users
    GET /users/user2
    POST /users/user1/score {"score": 500}
    DELETE /users

Команда "all" выполняет заранее заданный набор из 2 "хороших"
и 5 "плохих" запросов подряд (то, что требует отчёт задания).
Команда "exit" (или "quit") завершает работу. "help" — подсказка.

Лог каждого запроса пишется в формате:
    дата время [УРОВЕНЬ] сообщение
и в консоль, и в файл client_log.txt (дозаписью).
Уровень зависит от кода ответа: 2xx -> INFO, 4xx -> WARNING, 5xx -> ERROR.
"""

import json
import logging
import http.client

HOST = "127.0.0.1"
PORT = 8000
LOG_FILE = "client_log.txt"

logger = logging.getLogger("game_stats_client")
logger.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
logger.addHandler(_console_handler)


def request(method: str, path: str, raw_body: str | None = None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    headers = {}
    payload = None
    if raw_body is not None:
        payload = raw_body.encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = raw
        return resp.status, data
    finally:
        conn.close()


def run_command(method: str, path: str, raw_body: str | None = None) -> None:
    extra = f" body={raw_body}" if raw_body is not None else ""
    status, data = request(method, path, raw_body)
    message = f"{method} {path}{extra} -> {status} {data}"

    if 200 <= status < 300:
        logger.info(message)
    elif 400 <= status < 500:
        logger.warning(message)
    else:
        logger.error(message)


# 2 "хороших" + 5 "плохих" запросов — выполняются командой "all"
PRESET_CASES = [
    ("GET", "/users", None),
    ("GET", "/users/user2", None),
    ("GET", "/users/user99", None),                     # несуществующий пользователь
    ("GET", "/foo", None),                               # несуществующий маршрут
    ("POST", "/users/user1/score", '{"score": "abc"}'),  # неверный тип
    ("POST", "/users/user1/score", '{}'),                # нет поля score
    ("DELETE", "/users", None),                           # неподдерживаемый метод
]


HELP_TEXT = """\
Вводи запрос в формате: МЕТОД ПУТЬ [ТЕЛО]
Примеры:
  GET /users
  GET /users/user2
  GET /users/user99
  GET /foo
  POST /users/user1/score {"score": 500}
  POST /users/user1/score {"score": "abc"}
  DELETE /users

Команды:
  all        - выполнить набор из 2 хороших и 5 плохих запросов подряд
  help       - показать эту подсказку
  --s_help   - то же самое, что help
  exit       - выйти (quit тоже работает)
"""


def parse_and_run(line: str) -> None:
    parts = line.strip().split(maxsplit=2)
    if not parts:
        return
    method = parts[0].upper()
    if len(parts) < 2:
        print("Нужно указать путь, например: GET /users")
        return
    path = parts[1]
    raw_body = parts[2] if len(parts) > 2 else None
    run_command(method, path, raw_body)


def main() -> None:
    logger.info("=== Новая сессия клиента ===")
    print(HELP_TEXT)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print("Выход.")
            break
        if line.lower() in ("help", "--s_help"):
            print(HELP_TEXT)
            continue
        if line.lower() == "all":
            for method, path, raw_body in PRESET_CASES:
                run_command(method, path, raw_body)
            continue

        parse_and_run(line)


if __name__ == "__main__":
    main()
