import json
import socket

from client import HOST, PORT, request


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


def main():
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


if __name__ == "__main__":
    main()
