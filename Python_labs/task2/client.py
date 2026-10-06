import http.client

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


def main():
    print("Введите метод, путь и JSON-тело. Для выхода введите exit вместо метода.")
    print('Пример: POST, /users/user1/score, {"score": 500}')
    while True:
        try:
            method = input("HTTP-метод: ").strip().upper()
            if method in ("EXIT", "QUIT"):
                break
            path = input("Путь: ").strip()
            body = input("JSON-тело (или Enter): ")
            status, response = request(method, path, body)
            print(f"Код ответа: {status}\n{response}\n")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        except (OSError, http.client.HTTPException, ValueError) as error:
            print(f"Не удалось отправить запрос: {error}")


if __name__ == "__main__":
    main()
