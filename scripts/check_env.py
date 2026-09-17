"""팀 개발환경 점검: Python 버전, 패키지 import, sqlite-vec 로드, Ollama 연결, .env 키 존재 여부.
값은 출력하지 않는다.
"""
import sys
import urllib.request
from pathlib import Path

REQUIRED_PACKAGES = ["pydantic", "yaml", "requests", "pytest"]
REQUIRED_ENV_KEYS = ["MYSQL_DATABASE_URL", "GENERATION_API_KEY", "OLLAMA_HOST"]
OLLAMA_URL = "http://localhost:11434/api/tags"


def check_python_version():
    ok = sys.version_info[:2] == (3, 10)
    print(f"[{'OK' if ok else 'FAIL'}] Python {sys.version.split()[0]} (요구: 3.10.x)")
    return ok


def check_packages():
    all_ok = True
    for name in REQUIRED_PACKAGES:
        try:
            __import__(name)
            print(f"[OK] import {name}")
        except ImportError:
            print(f"[FAIL] import {name}")
            all_ok = False
    return all_ok


def check_sqlite_vec():
    try:
        import sqlite3
        import sqlite_vec

        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        print("[OK] sqlite-vec 로드")
        return True
    except Exception as e:
        print(f"[FAIL] sqlite-vec 로드: {e}")
        return False


def check_ollama():
    try:
        with urllib.request.urlopen(OLLAMA_URL, timeout=2):
            print("[OK] Ollama 연결")
            return True
    except Exception as e:
        print(f"[FAIL] Ollama 연결: {e}")
        return False


def check_env_keys():
    env_path = Path(".env")
    if not env_path.exists():
        print("[FAIL] .env 파일 없음")
        return False
    keys_present = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            keys_present.add(line.split("=", 1)[0].strip())
    all_ok = True
    for key in REQUIRED_ENV_KEYS:
        ok = key in keys_present
        print(f"[{'OK' if ok else 'FAIL'}] .env 키 존재: {key}")
        all_ok = all_ok and ok
    return all_ok


def main():
    results = [
        check_python_version(),
        check_packages(),
        check_sqlite_vec(),
        check_ollama(),
        check_env_keys(),
    ]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
