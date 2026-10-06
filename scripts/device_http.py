"""Send a sample recognition result through the existing HTTP scan API.

Run from repository root: python -m scripts.device_http --help
"""
import argparse
import math
import socket

from shiftlink.vision.classify import post_scan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Example: http://192.168.50.1:8000")
    parser.add_argument("--label", required=True, help="Equipment class in the server catalog")
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--device-id", default=socket.gethostname())
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()
    if not args.server.startswith("http://"):
        parser.error("--server must start with http://")
    if not math.isfinite(args.confidence) or not 0 <= args.confidence <= 1:
        parser.error("--confidence must be between 0 and 1")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not 0 < len(args.device_id) <= 64:
        parser.error("--device-id must be a 1..64 char string")
    if not post_scan(args.server, args.label, args.confidence, args.device_id, args.timeout):
        raise SystemExit(1)
    print("HTTP 201: recognition result recorded")


if __name__ == "__main__":
    main()
