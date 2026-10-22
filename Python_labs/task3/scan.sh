#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Semgrep уже установлен в окружении ДЗ-3.
if [ -x .venv/bin/semgrep ]; then
  export PATH="$PWD/.venv/bin:$PATH"
elif ! command -v semgrep >/dev/null; then
  if [ -x "$HOME/Documents/dz-3/.venv/bin/semgrep" ]; then
    export PATH="$HOME/Documents/dz-3/.venv/bin:$PATH"
  else
    printf 'Semgrep не найден. Активируйте окружение с установленным Semgrep.\n' >&2
    exit 1
  fi
fi

RULES_COMMIT=17e31e11ebac99fb7dfe1cd288f7a32151b6f3f9
RULES_DIR=semgrep-rules-yaml
if [ ! -f "$RULES_DIR/.version" ] || [ "$(cat "$RULES_DIR/.version")" != "$RULES_COMMIT" ]; then
  printf 'Скачиваем официальные Python-правила одним архивом…\n'
  staging=$(mktemp -d "${TMPDIR:-/tmp}/task3-rules.XXXXXX")
  trap 'rm -rf "$staging"' EXIT
  curl --fail --location --silent --show-error \
    --connect-timeout 15 --max-time 180 --retry 2 \
    "https://codeload.github.com/semgrep/semgrep-rules/tar.gz/$RULES_COMMIT" \
    --output "$staging/rules.tar.gz"
  tar -xzf "$staging/rules.tar.gz" -C "$staging" "semgrep-rules-$RULES_COMMIT/python"
  # Копируем только YAML с сохранением структуры. Работает на macOS.
  python3 - "$staging/semgrep-rules-$RULES_COMMIT/python" "$RULES_DIR" <<'PY'
from pathlib import Path
import shutil
import sys
source, target = map(Path, sys.argv[1:])
if target.exists():
    shutil.rmtree(target)
for path in source.rglob('*'):
    if path.suffix in {'.yaml', '.yml'}:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
PY
  printf '%s\n' "$RULES_COMMIT" > "$RULES_DIR/.version"
  rm -rf "$staging"
  trap - EXIT
else
  printf 'Используем уже скачанные Python-правила.\n'
fi

# Для окружений Python на macOS используем доступный набор сертификатов.
semgrep_python="$(dirname "$(command -v semgrep)")/python"
if [ -z "${SSL_CERT_FILE:-}" ] && [ -x "$semgrep_python" ]; then
  if cert_file=$("$semgrep_python" -m certifi 2>/dev/null); then
    export SSL_CERT_FILE="$cert_file"
  fi
fi

printf 'Проверяем main.py…\n'
semgrep scan --config "$RULES_DIR/" --metrics=off --disable-version-check --oss-only \
  --json --output semgrep-report.json main.py
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path('semgrep-report.json').read_text())
print(f"Срабатываний: {len(report['results'])}. Ошибок анализа: {len(report['errors'])}.")
print('Результат: semgrep-report.json. Таблица и выводы: report.md.')
if report['errors']:
    raise SystemExit('Есть ошибки анализа. Проверьте semgrep-report.json.')
PY
