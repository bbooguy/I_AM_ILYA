#!/usr/bin/env python3
"""
Интерактивный клиент для задания №1.

Показывает меню, пользователь выбирает номер запроса (или "0" — выполнить
все по очереди). Клиент шлёт выбранный запрос на сервер (server.py должен
быть уже запущен на 127.0.0.1:8000), печатает результат в консоль и
одновременно дописывает его в лог-файл client_log.txt.

Набор запросов: 2 "хороших" (успешных) и 5 "плохих" (ожидаемо
завершающихся ошибкой, но без падения сервера).
"""

import json
import http.client
from datetime import datetime

HOST = "127.0.0.1"
PORT = 8000
LOG_FILE = "client_log.txt"


def request(method: str, path: str, body: dict | None = None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    headers = {}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
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


def log(text: str = "") -> None:
    """Печатает строку в консоль и дописывает её в лог-файл (в конец, не затирая старое)."""
    print(text)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def run_case(title: str, method: str, path: str, body: dict | None = None) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status, data = request(method, path, body)
    log(f"[{timestamp}] {title}")
    extra = f" body={body}" if body is not None else ""
    log(f"    Запрос: {method} {path}{extra}")
    log(f"    Код ответа: {status}")
    log(f"    Тело: {data}")
    log("")


# 2 "хороших" + 5 "плохих" запросов
CASES = {
    "1": ("[хороший] GET /users", "GET", "/users", None),
    "2": ("[хороший] GET /users/user2", "GET", "/users/user2", None),
    "3": ("[плохой] GET /users/user99 — несуществующий пользователь", "GET", "/users/user99", None),
    "4": ("[плохой] GET /foo — несуществующий маршрут", "GET", "/foo", None),
    "5": ("[плохой] POST /users/user1/score {'score': 'abc'} — неверный тип", "POST", "/users/user1/score", {"score": "abc"}),
    "6": ("[плохой] POST /users/user1/score без поля score", "POST", "/users/user1/score", {}),
    "7": ("[плохой] DELETE /users — неподдерживаемый метод", "DELETE", "/users", None),
}


def print_menu() -> None:
    print("\n=== Меню клиента ===")
    for key, (title, *_rest) in CASES.items():
        print(f"{key}. {title}")
    print("0. Выполнить все запросы по очереди")
    print("q. Выход")


def main() -> None:
    log(f"=== Новая сессия клиента: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    while True:
        print_menu()
        choice = input("\nВыбери номер запроса: ").strip().lower()

        if choice == "q":
            print("Выход.")
            break

        if choice == "0":
            for key in CASES:
                title, method, path, body = CASES[key]
                run_case(title, method, path, body)
            continue

        case = CASES.get(choice)
        if case is None:
            print("Нет такого пункта меню, попробуй ещё раз.")
            continue

        title, method, path, body = case
        run_case(title, method, path, body)


if __name__ == "__main__":
    main()
