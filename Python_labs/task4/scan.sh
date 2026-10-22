#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
RULES_COMMIT=17e31e11ebac99fb7dfe1cd288f7a32151b6f3f9
# Отдельный кэш не затрагивает старый репозиторий semgrep-rules.
RULES_DIR=".scan-cache/rules-$RULES_COMMIT"
if [ ! -f "$RULES_DIR/.ready" ] || [ ! -d "$RULES_DIR/python" ] || [ ! -d "$RULES_DIR/dockerfile" ]; then
  printf 'Скачиваем официальные правила Semgrep одним архивом…\n'
  mkdir -p .scan-cache
  staging=$(mktemp -d .scan-cache/download.XXXXXX)
  trap 'rm -rf "$staging"' EXIT
  curl --fail --location --silent --show-error \
    --connect-timeout 15 --max-time 180 --retry 2 \
    "https://codeload.github.com/semgrep/semgrep-rules/tar.gz/$RULES_COMMIT" \
    --output "$staging/rules.tar.gz"
  tar -xzf "$staging/rules.tar.gz" -C "$staging" \
    "semgrep-rules-$RULES_COMMIT/python" \
    "semgrep-rules-$RULES_COMMIT/dockerfile"
  # Сначала полностью готовим кэш, затем заменяем старую копию.
  touch "$staging/semgrep-rules-$RULES_COMMIT/.ready"
  rm -rf "$RULES_DIR"
  mv "$staging/semgrep-rules-$RULES_COMMIT" "$RULES_DIR"
  rm -rf "$staging"
  trap - EXIT
else
  printf 'Используем уже скачанные правила Semgrep.\n'
fi
printf '\nПроверяем Python-код…\n'
semgrep scan --config "$RULES_DIR/python" --metrics=off --disable-version-check --oss-only \
  --json --output semgrep-python.json main.py bank_client.py setup.py
printf '\nПроверяем Dockerfile…\n'
semgrep scan --config "$RULES_DIR/dockerfile" --metrics=off --disable-version-check --oss-only \
  --json --output semgrep-docker.json Dockerfile
