"""Run the local synthetic MES demo."""

import argparse
from pathlib import Path
from .server import serve


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic local MES demonstration")
    parser.add_argument("--host", default="127.0.0.1", help="Jetson에서 파이가 접속하려면 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, help="SQLite history path")
    parser.add_argument("--api-only", action="store_true", help="Serve APIs only; PDA files are hosted on Raspberry Pi")
    args = parser.parse_args()
    serve(host=args.host, port=args.port, db_path=args.db, api_only=args.api_only)
