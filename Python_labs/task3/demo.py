#!/usr/bin/env python3
"""Пошаговая демонстрация проверки main.py через Semgrep."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def pause(enabled):
    if enabled:
        input("\nНажмите Enter, чтобы продолжить… ")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pause", action="store_true", help="Без остановок между этапами")
    parser.add_argument("--report-only", action="store_true", help="Показать сохранённый JSON без новой проверки")
    args = parser.parse_args()
    interactive = sys.stdin.isatty() and not args.no_pause

    print("ДЗ 3. Демонстрация Semgrep", flush=True)
    print("Проверяем исходный main.py. Сервер запускать не требуется.", flush=True)
    if args.report_only:
        print("Режим просмотра: используется сохранённый отчёт, новой проверки нет.")
    else:
        print("\n1. Подготовка и запуск проверки", flush=True)
        for name in ("main.py", "scan.sh", "requirements.txt"):
            if not (ROOT / name).is_file():
                raise RuntimeError(f"В папке скрипта отсутствует {name}")
        if not shutil.which("git"):
            raise RuntimeError("Не установлен Git. На Mac выполните xcode-select --install.")
        env = os.environ.copy()
        venv = ROOT / ".venv"
        if (venv / "bin/semgrep").is_file():
            executable = str(venv / "bin/semgrep")
        else:
            executable = shutil.which("semgrep")
        if not executable:
            print("Создаётся .venv и устанавливается Semgrep. Нужен интернет.", flush=True)
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
            subprocess.run([str(venv / "bin/python"), "-m", "pip", "install", "-r",
                            str(ROOT / "requirements.txt")], check=True)
            executable = str(venv / "bin/semgrep")
        env["PATH"] = str(Path(executable).parent) + os.pathsep + env.get("PATH", "")
        # Служебные файлы остаются в папке работы, а не в домашнем каталоге.
        cache = ROOT / ".demo-cache"
        cache.mkdir(exist_ok=True)
        env.setdefault("SEMGREP_LOG_FILE", str(cache / "semgrep.log"))
        env.setdefault("SEMGREP_SETTINGS_FILE", str(cache / "settings.yml"))
        python = Path(executable).parent / "python"
        if python.is_file() and "SSL_CERT_FILE" not in env:
            result = subprocess.run([str(python), "-m", "certifi"], capture_output=True, text=True)
            if result.returncode == 0:
                env["SSL_CERT_FILE"] = result.stdout.strip()
        pause(interactive)
        subprocess.run(["bash", "scan.sh"], cwd=ROOT, env=env, check=True)

    print("\n2. Результаты из semgrep-report.json")
    report = json.loads((ROOT / "semgrep-report.json").read_text())
    findings = report.get("results", [])
    errors = report.get("errors", [])
    print(f"Semgrep: {report.get('version', 'не указана')}")
    print(f"Срабатываний: {len(findings)}. Ошибок анализа: {len(errors)}.")
    if errors:
        print(json.dumps(errors, ensure_ascii=False, indent=2))
        raise RuntimeError("В отчёте есть ошибки анализа; результаты могут быть неполными.")
    pause(interactive)

    print("\n3. Срабатывания и соответствующий код")
    lines = (ROOT / "main.py").read_text().splitlines()
    for number, finding in enumerate(findings, 1):
        start = finding["start"]["line"]
        end = finding["end"]["line"]
        extra = finding["extra"]
        print(f"\n[{number}/{len(findings)}] {extra['severity']} — {finding['check_id']}")
        print(f"Файл: {finding['path']}, строка: {start}")
        print("Сообщение:", extra["message"])
        if finding["path"] == "main.py":
            for index in range(max(0, start - 2), min(len(lines), end + 1)):
                marker = ">" if start <= index + 1 <= end else " "
                print(f"{marker} {index + 1:3} | {lines[index]}")
        pause(interactive)

    print("\n4. Таблица и выводы из report.md\n")
    print((ROOT / "report.md").read_text())
    print("\nДемонстрация завершена. JSON содержит результаты инструмента, report.md — их разбор.")
    print("report.md не пересоздаётся автоматически: если результаты проверки изменятся, обновите таблицу.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nДемонстрация остановлена.")
        sys.exit(130)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)
