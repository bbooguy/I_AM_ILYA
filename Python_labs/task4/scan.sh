#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
RULES_COMMIT=17e31e11ebac99fb7dfe1cd288f7a32151b6f3f9
RULES_DIR=${RULES_DIR:-semgrep-rules}
if [ ! -d "$RULES_DIR/.git" ]; then
  git clone --filter=blob:none --no-checkout https://github.com/semgrep/semgrep-rules.git "$RULES_DIR"
fi
git -C "$RULES_DIR" checkout "$RULES_COMMIT" -- python dockerfile
semgrep scan --config "$RULES_DIR/python" --metrics=off --disable-version-check --oss-only \
  --json --output semgrep-python.json main.py bank_client.py setup.py
semgrep scan --config "$RULES_DIR/dockerfile" --metrics=off --disable-version-check --oss-only \
  --json --output semgrep-docker.json Dockerfile
