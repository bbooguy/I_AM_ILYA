import http.client
import subprocess
import sys
from pathlib import Path

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


def interactive():
    print("Введите метод, путь и JSON-тело. Введите help вместо метода для примеров, exit — для выхода.")
    print('Пример: POST, /users/user1/score, {"score": 500}')
    while True:
        try:
            method = input("HTTP-метод: ").strip().upper()
            if method in ("EXIT", "QUIT"):
                break
            if method == "HELP":
                print('GET /users — все пользователи; тело: Enter')
                print('GET /users/user2 — один пользователь; тело: Enter')
                print('POST /users/user1/score — добавить очки; тело: {"score": 500}')
                print('GET /users/user99 — ошибка 404; тело: Enter')
                print('POST /users/user1/score — ошибка 400; тело: {"score": "abc"}')
                print('DELETE /users — ошибка 405; тело: Enter')
                print('Метод, путь и тело вводятся отдельно. exit — выход.\n')
                continue
            path = input("Путь: ").strip()
            body = input("JSON-тело (или Enter): ")
            status, response = request(method, path, body)
            print(f"Код ответа: {status}\n{response}\n")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        except (OSError, http.client.HTTPException, ValueError) as error:
            print(f"Не удалось отправить запрос: {error}")


def main():
    print("Запуск автоматических проверок...", flush=True)
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("edge_cases.py"))])
    if result.returncode != 0:
        print("Автоматические проверки не прошли. Проверьте, что сервер запущен.")
        return result.returncode
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
