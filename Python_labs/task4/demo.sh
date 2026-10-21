#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
trap 'printf "\nДемонстрация остановлена из-за ошибки на строке %s. См. сообщение выше.\n" "$LINENO" >&2' ERR

printf '\n1. Проверяем Docker\n'
command -v docker >/dev/null || { printf 'Установите Docker Desktop.\n' >&2; exit 1; }
if ! docker info >/dev/null 2>&1; then
  printf 'Запускаем Docker Desktop…\n'
  if docker desktop start --help >/dev/null 2>&1; then
    docker desktop start --timeout 60
  else
    open -a Docker
  fi
  for ((i=0; i<60; i++)); do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if ! docker info >/dev/null 2>&1; then
    printf "Docker Desktop открыт, но движок ещё не готов. Дождитесь Engine running и повторите bash demo.sh.\n" >&2
    exit 1
  fi
fi
docker compose version

printf '\n2. Создаём пароли, собираем и запускаем сервер\n'
python3 setup.py
docker compose up --build -d --wait --wait-timeout 90
docker compose ps

printf '\n3. Проверяем вход и запрет чужой истории на запущенном сервере\n'
docker compose exec -T bank python - <<'PY'
from pathlib import Path
import socket
password = Path('/run/secrets/alice_password').read_text().strip()
with socket.create_connection(('127.0.0.1', 9999), timeout=10) as sock:
    stream = sock.makefile('rb')
    assert stream.readline() == b'BANK SERVER READY\n', 'Сервер не готов'
    def command(text):
        sock.sendall((text + '\n').encode())
        return stream.readline().decode().strip()
    answer = command('LOGIN alice ' + password)
    if not answer.startswith('OK|'):
        raise RuntimeError('Вход отклонён: ' + answer + '. При лимите попыток подождите минуту.')
    print('Вход alice: OK')
    balance = command('BALANCE')
    assert balance.startswith('OK|'), balance
    print('Баланс:', balance)
    denied = command('HISTORY 3')
    assert denied == 'ERR|Access denied', denied
    print('Чужая история:', denied)
    assert command('QUIT') == 'BYE'
PY

printf '\n4. Запускаем 16 тестов защиты в отдельном контейнере\n'
# Тесты работают с временными базами и не меняют счета запущенного сервера.
docker compose run --rm -T \
  -v "$PWD/test_server.py:/app/test_server.py:ro" \
  -v "$PWD/bank_client.py:/app/bank_client.py:ro" \
  bank python -m unittest -v test_server

printf '\n5. Находим Semgrep\n'
if [ -x .venv/bin/semgrep ]; then
  export PATH="$PWD/.venv/bin:$PATH"
elif command -v semgrep >/dev/null; then
  :
elif [ -x "$HOME/Documents/dz-3/.venv/bin/semgrep" ]; then
  export PATH="$HOME/Documents/dz-3/.venv/bin:$PATH"
else
  printf 'Semgrep не найден. Устанавливаем один раз в .venv…\n'
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements-dev.txt
  export PATH="$PWD/.venv/bin:$PATH"
fi
semgrep --version
# Используем сертификаты окружения Semgrep, если они доступны.
semgrep_python="$(dirname "$(command -v semgrep)")/python"
if [ -z "${SSL_CERT_FILE:-}" ] && [ -x "$semgrep_python" ]; then
  if cert_file=$("$semgrep_python" -m certifi 2>/dev/null); then
    export SSL_CERT_FILE="$cert_file"
  fi
fi
mkdir -p .scan-cache
export SEMGREP_LOG_FILE="$PWD/.scan-cache/semgrep.log"
export SEMGREP_SETTINGS_FILE="$PWD/.scan-cache/settings.yml"

printf '\n6. Проверяем Python и Dockerfile через Semgrep\n'
bash scan.sh
python3 - <<'PY'
import json
from pathlib import Path
for name in ('semgrep-python.json', 'semgrep-docker.json'):
    data = json.loads(Path(name).read_text())
    errors = data.get('errors', [])
    print(f"{name}: срабатываний {len(data.get('results', []))}, ошибок анализа {len(errors)}")
    if errors:
        raise SystemExit('Есть ошибки анализа: проверьте JSON-отчёт.')
PY

printf '\n7. Последние события в журнале сервера\n'
docker compose logs --tail 12 bank
printf '\nГотово. Сервер остаётся запущенным.\n'
printf 'Покажите report.md и два JSON-отчёта Semgrep.\n'
printf 'Для ручной работы: python3 bank_client.py alice\n'
printf 'Для остановки с сохранением базы: docker compose down\n'
