#!/usr/bin/env python3
"""
Клиент для задания №1.

Делает несколько "хороших" и заведомо "плохих" запросов к серверу
(server.py должен быть уже запущен на 127.0.0.1:8000) и печатает
код ответа и тело для каждого случая.
"""

import json
import http.client

HOST = "127.0.0.1"
PORT = 8000


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


def show(title: str, status: int, data) -> None:
    print(f"--- {title} ---")
    print(f"Код ответа: {status}")
    print(f"Тело: {data}")
    print()


if __name__ == "__main__":
    # 1. корректный запрос списка
    show("GET /users", *request("GET", "/users"))

    # 2. корректный запрос одного пользователя
    show("GET /users/user2", *request("GET", "/users/user2"))

    # 3. запрос к несуществующему пользователю
    show("GET /users/user99 (несуществующий пользователь)", *request("GET", "/users/user99"))

    # 4. корректное начисление очков
    show("POST /users/user1/score {'score': 500}", *request("POST", "/users/user1/score", {"score": 500}))

    # 5. заведомо некорректный запрос — score не число
    show(
        "POST /users/user1/score {'score': 'abc'} (score не число)",
        *request("POST", "/users/user1/score", {"score": "abc"}),
    )
