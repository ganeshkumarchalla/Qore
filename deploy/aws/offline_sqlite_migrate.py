"""Copy a stopped QORE container's SQLite data into a host-mounted database.

Copy the entire /app/data directory from the stopped container first so WAL
files are available. This script refuses to overwrite an existing target.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    if not args.source.is_file() or args.target.exists():
        raise SystemExit("Source must exist and target must not exist")
    if args.target.parent.stat().st_mode & 0o077:
        raise SystemExit("Target directory must be private")

    source = sqlite3.connect(f"file:{args.source}?mode=ro", uri=True)
    try:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Source SQLite integrity check failed")
        target = sqlite3.connect(args.target)
        try:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("Target SQLite integrity check failed")
        finally:
            target.close()
    finally:
        source.close()
    os.chmod(args.target, 0o600)
    print("PASS offline SQLite backup and integrity checks")


if __name__ == "__main__":
    main()
