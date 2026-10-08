import http.client
import json
import logging
from pathlib import Path
import socket
import sys
from http import HTTPStatus

HOST = "127.0.0.1"
PORT = 8000

logging.basicConfig(
    filename=Path(__file__).with_name("client.log"),
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("client")


def request(method, path, raw_body=""):
    logger.info("Запрос: %s %s; тело: %s", method, path, raw_body or "(пусто)")
    connection = http.client.HTTPConnection(HOST, PORT, timeout=10)
    try:
        body = raw_body.encode("utf-8") if raw_body else None
        connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        level = logging.ERROR if response.status >= 500 else logging.WARNING if response.status >= 400 else logging.INFO
        logger.log(level, "Ответ: %s %s; тело: %s", response.status, response.reason, text)
        return response.status, text
    except (OSError, http.client.HTTPException, ValueError) as error:
        logger.error("Ошибка запроса: %s", error)
        raise
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
        ("GET", "/error", "", 500),
        ("POST", "/users/user99/score", '{"score": 1}', 404),
        ("POST", "/foo", "", 404),
        ("POST", "/users/user1/score", "", 400),
        ("POST", "/users/user1/score", '{"score":', 400),
        ("DELETE", "/users", "", 405),
        ("PUT", "/users", "", 405),
        ("PATCH", "/users", "", 405),
        ("OPTIONS", "/users", "", 405),
        ("CUSTOM", "/users", "", 405),
        ("GET", "/users/user1/score", "", 405),
        ("POST", "/users/user1", "", 405),
        ("POST", "/users", "", 405),
    ]
    for body in ('{}', '[]', 'null', '42', '{"score": "abc"}', '{"score": "100"}',
                 '{"score": true}', '{"score": 1.5}', '{"score": -1}'):
        cases.append(("POST", "/users/user1/score", body, 400))
    for case in cases:
        check(*case)

    logger.info("Проверка неполной отправки тела запроса")
    with socket.create_connection((HOST, PORT), timeout=10) as connection:
        connection.sendall(b'POST /users/user1/score HTTP/1.0\r\nContent-Length: 100\r\n\r\n{"score": 999}')
        connection.shutdown(socket.SHUT_WR)
        response = http_response(connection)
        assert response.status == 400
        assert "error" in json.loads(response.read())

    with socket.create_connection((HOST, PORT), timeout=10) as connection:
        connection.sendall(b'POST /users/user1/score HTTP/1.0\r\nContent-Length: 100\r\n\r\n{"score":')
    logger.warning("Соединение намеренно закрыто посреди отправки тела")
    final = check("GET", "/users/user1", "", 200)
    assert final == after, (final, after)
    print("Все проверки пройдены; сервер отвечает после ошибок и обрыва соединения.")

def http_response(connection):
    from http.client import HTTPResponse
    response = HTTPResponse(connection)
    response.begin()
    return response


def run_tests():
    logger.info("Запуск автоматических проверок")
    print("Запуск автоматических проверок...")
    try:
        perform_tests()
    except (AssertionError, OSError, http.client.HTTPException, ValueError) as error:
        logger.error("Проверки не прошли: %s", error)
        print(f"Проверки не прошли: {error}")
        return 1
    logger.info("Все автоматические проверки пройдены")
    return 0


def show_help():
    print("200 OK — успешный запрос:")
    print("  GET /users")
    print("  GET /users/user2")
    print('  POST /users/user1/score {"score": 500}')
    print("400 Bad Request — неверное тело запроса:")
    print('  POST /users/user1/score {"score": "abc"}')
    print('  POST /users/user1/score {"score":')
    print("  POST /users/user1/score")
    print("404 Not Found — пользователь или маршрут не найден:")
    print("  GET /users/user99")
    print("  GET /foo")
    print("405 Method Not Allowed — неподходящий метод:")
    print("  DELETE /users")
    print("  GET /users/user1/score")
    print("500 Internal Server Error — демонстрация внутренней ошибки:")
    print("  GET /error")
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
    if mode == "test":
        return status
    interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
