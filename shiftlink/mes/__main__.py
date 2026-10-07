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
    parser.add_argument('--random-faults', action='store_true', help='Use varied synthetic sensors and random performance warnings')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--run-nonce', help='Replay identifier; omitted values create a fresh sensor trajectory')
    parser.add_argument('--fault-hazard', type=float, default=.015, help='Per eligible equipment per tick probability (0..1)')
    args = parser.parse_args()
    if not 0 <= args.fault_hazard <= 1:
        parser.error('--fault-hazard must be within 0..1')
    serve(host=args.host, port=args.port, db_path=args.db, api_only=args.api_only,
          random_faults=args.random_faults, seed=args.seed, run_nonce=args.run_nonce, fault_hazard=args.fault_hazard)
