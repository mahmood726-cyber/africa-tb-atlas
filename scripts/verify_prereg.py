"""Verify that preregistered files have not drifted from their stamped sha256.

Used as a CI/preflight gate AFTER OTS stamping (Task 6). Fails closed on drift.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path,
                    help="JSON file mapping relpath -> expected sha256")
    ap.add_argument("--root", default=".", type=Path,
                    help="Root dir for relpaths in manifest")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    drift = []
    for relpath, expected in manifest.items():
        p = args.root / relpath
        if not p.exists():
            drift.append(f"  MISSING: {relpath}")
            continue
        actual = sha256_of(p)
        if actual != expected:
            drift.append(f"  DRIFT: {relpath} (expected {expected[:16]}... got {actual[:16]}...)")

    if drift:
        print("DRIFT detected:", file=sys.stderr)
        for d in drift:
            print(d, file=sys.stderr)
        return 1
    print(f"OK: {len(manifest)} preregistered file(s) match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
