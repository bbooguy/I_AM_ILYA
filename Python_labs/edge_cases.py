#!/usr/bin/env python3
"""
Проверки устойчивости сервера для задания №1.

http.client всегда собирает синтаксически корректные HTTP-запросы,
поэтому "битый" JSON и обрыв соединения посреди отправки данных
эмулируются через сырые сокеты.

Запускать при уже работающем server.py (127.0.0.1:8000).
"""

import json
import socket
import http.client

HOST = "127.0.0.1"
PORT = 8000


def raw_broken_json() -> str:
    """POST с намеренно битым (обрезанным) JSON в теле."""
    body = b'{"score": '
    request_bytes = (
        f"POST /users/user1/score HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode() + body
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(request_bytes)
        return s.recv(4096).decode(errors="replace")


def raw_no_body() -> str:
    """POST вообще без тела (Content-Length: 0)."""
    request_bytes = (
        f"POST /users/user1/score HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        f"Content-Length: 0\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(request_bytes)
        return s.recv(4096).decode(errors="replace")


def dropped_connection() -> str:
    """
    Клиент заявляет Content-Length больше, чем реально отправляет,
    и обрывает соединение, не дождавшись ответа сервера.
    Проверяем только то, что сервер после этого продолжает работать.
    """
    partial_body = b'{"score":'
    request_bytes = (
        f"POST /users/user1/score HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: 100\r\n\r\n"
    ).encode() + partial_body
    with socket.create_connection((HOST, PORT), timeout=5) as s:
        s.sendall(request_bytes)
        # закрываем сокет сразу, не дожидаясь ответа — имитация обрыва связи
    return "соединение намеренно оборвано клиентом, не дожидаясь ответа"


def server_is_alive() -> tuple[int, str]:
    """Обычный GET /users — проверка, что сервер не упал после сбоев выше."""
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        conn.request("GET", "/users")
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8")
    finally:
        conn.close()


if __name__ == "__main__":
    print("--- POST с битым JSON ---")
    print(raw_broken_json())
    print()

    print("--- POST без тела ---")
    print(raw_no_body())
    print()

    print("--- Обрыв соединения клиентом посреди отправки ---")
    print(dropped_connection())
    print()

    status, body = server_is_alive()
    print("--- Проверка, что сервер жив после всех сбоев (GET /users) ---")
    print(f"Код ответа: {status}")
    print(f"Тело: {body}")
