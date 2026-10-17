#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
RULES_COMMIT=17e31e11ebac99fb7dfe1cd288f7a32151b6f3f9
RULES_DIR=${RULES_DIR:-semgrep-rules}
if [ ! -d "$RULES_DIR/.git" ]; then
    git clone --filter=blob:none --no-checkout https://github.com/semgrep/semgrep-rules.git "$RULES_DIR"
fi
git -C "$RULES_DIR" checkout "$RULES_COMMIT" -- python
# Копирование YAML с сохранением структуры, совместимое с Linux и macOS.
python3 - "$RULES_DIR" <<'PY'
from pathlib import Path
import shutil
import sys
source = Path(sys.argv[1]) / "python"
target = Path("semgrep-rules-yaml")
if target.exists():
    shutil.rmtree(target)
for path in source.rglob("*"):
    if path.suffix in {".yaml", ".yml"}:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
PY
semgrep scan --config semgrep-rules-yaml/ \
    --metrics=off --disable-version-check --oss-only \
    --json --output semgrep-report.json main.py
