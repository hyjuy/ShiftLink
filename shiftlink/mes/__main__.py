"""Run the local synthetic MES demo."""

import argparse
from pathlib import Path
from .server import serve


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic local MES demonstration")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, help="SQLite history path")
    args = parser.parse_args()
    serve(port=args.port, db_path=args.db)
