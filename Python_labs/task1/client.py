import http.client
import json
import socket
import sys
from http import HTTPStatus

HOST = "127.0.0.1"
PORT = 8000


def request(method, path, raw_body=""):
    connection = http.client.HTTPConnection(HOST, PORT, timeout=10)
    try:
        body = raw_body.encode("utf-8") if raw_body else None
        connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def check(method, path, body, expected):
    status, raw = request(method, path, body)
    data = json.loads(raw)
    assert status == expected, (method, path, status, data)
    if expected != 200:
        assert isinstance(data.get("error"), str), data
    print(f"{method} {path} {body} -> {status}: {raw}")

    status, _ = request("GET", "/users")
    assert status == 200
    return data

def perform_tests():
    users = check("GET", "/users", "", 200)
    assert len(users) == 3
    before = check("GET", "/users/user1", "", 200)
    after = check("POST", "/users/user1/score", '{"score": 500}', 200)
    assert after["score"] == before["score"] + 500
    cases = [
        ("GET", "/users/user99", "", 404),
        ("GET", "/foo", "", 404),
        ("POST", "/users/user99/score", '{"score": 1}', 404),
        ("POST", "/foo", "", 404),
        ("POST", "/users/user1/score", "", 400),
        ("POST", "/users/user1/score", '{"score":', 400),
        ("DELETE", "/users", "", 405),
        ("OPTIONS", "/users", "", 405),
        ("CUSTOM", "/users", "", 405),
        ("GET", "/users/user1/score", "", 405),
        ("POST", "/users/user1", "", 405),
        ("POST", "/users", "", 405),
    ]
    for body in ('{}', '[]', 'null', '42', '{"score": "abc"}', '{"score": "100"}',
                 '{"score": true}', '{"score": NaN}', '{"score": Infinity}'):
        cases.append(("POST", "/users/user1/score", body, 400))
    for case in cases:
        check(*case)

    with socket.create_connection((HOST, PORT), timeout=10) as connection:
        connection.sendall(b'POST /users/user1/score HTTP/1.0\r\nContent-Length: 100\r\n\r\n{"score": 999}')
        connection.shutdown(socket.SHUT_WR)
        response = http_response(connection)
        assert response.status == 400
        assert "error" in json.loads(response.read())

    with socket.create_connection((HOST, PORT), timeout=10) as connection:
        connection.sendall(b'POST /users/user1/score HTTP/1.0\r\nContent-Length: 100\r\n\r\n{"score":')
    final = check("GET", "/users/user1", "", 200)
    assert final == after, (final, after)
    fractional = check("POST", "/users/user1/score", '{"score": 1.5}', 200)
    assert fractional["score"] == after["score"] + 1.5
    negative = check("POST", "/users/user1/score", '{"score": -1}', 200)
    assert negative["score"] == fractional["score"] - 1
    print("Все проверки пройдены; сервер отвечает после ошибок и обрыва соединения.")

def http_response(connection):
    from http.client import HTTPResponse
    response = HTTPResponse(connection)
    response.begin()
    return response


def run_tests():
    print("Запуск автоматических проверок...")
    try:
        perform_tests()
    except (AssertionError, OSError, http.client.HTTPException, ValueError) as error:
        print(f"Проверки не прошли: {error}")
        return 1
    return 0


def show_help():
    print("GET /users")
    print("GET /users/user2")
    print('POST /users/user1/score {"score": 500}')
    print("GET /users/user99")
    print("GET /foo")
    print('POST /users/user1/score {"score": "abc"}')
    print("DELETE /users")
    print("help — примеры; test — повторить автотесты; exit — выход")


def interactive():
    print("Введите запрос одной строкой. help — примеры, test — автотесты, exit — выход.")
    while True:
        try:
            command = input("> ").strip()
            if not command:
                continue
            if command.lower() in ("exit", "quit"):
                break
            if command.lower() == "help":
                show_help()
                continue
            if command.lower() == "test":
                run_tests()
                continue
            parts = command.split(maxsplit=2)
            if len(parts) < 2:
                print("Формат: METHOD /path [JSON]")
                continue
            method, path = parts[:2]
            body = parts[2] if len(parts) == 3 else ""
            status, response = request(method.upper(), path, body)
            print(f"{status} {HTTPStatus(status).phrase}\n{response}\n")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        except (OSError, http.client.HTTPException, ValueError) as error:
            print(f"Не удалось отправить запрос: {error}")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) == 2 else "full"
    if len(sys.argv) > 2 or mode not in ("full", "test", "interactive", "manual"):
        print("Запуск: python3 client.py [full|test|interactive]")
        return 1
    if mode in ("interactive", "manual"):
        interactive()
        return 0
    status = run_tests()
    if mode == "test" or status != 0:
        return status
    try:
        choice = input("Перейти в ручной режим? [да/нет]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nВыход.")
        return 0
    if choice in ("да", "д", "yes", "y"):
        interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
