"""Manual SQLite backup, integrity check, and safe offline restore."""
import argparse
from contextlib import closing
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.environ.get("RELOOP_DB", ROOT / "reloop.sqlite3")).resolve()
BACKUP_DIR = Path(os.environ.get("RELOOP_BACKUP_DIR", ROOT / "backups")).resolve()

def integrity(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result}")
    return True

def backup():
    if not DB.is_file():
        raise FileNotFoundError(f"Database not found: {DB}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"reloop-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with closing(sqlite3.connect(DB)) as source, closing(sqlite3.connect(tmp)) as target:
        source.backup(target)
    integrity(tmp)
    tmp.replace(dest)
    print(f"Backup created and verified: {dest}")

def restore(source):
    if not source.is_file():
        raise FileNotFoundError(f"Backup not found: {source}")
    integrity(source)
    DB.parent.mkdir(parents=True, exist_ok=True)
    temp = DB.with_suffix(DB.suffix + ".restore.tmp")
    with closing(sqlite3.connect(source)) as original, closing(sqlite3.connect(temp)) as target:
        original.backup(target)
    integrity(temp)
    if DB.exists():
        safety = DB.with_suffix(DB.suffix + ".before-restore")
        if safety.exists():
            raise FileExistsError(f"Safety copy already exists; move it before retrying: {safety}")
        DB.replace(safety)
    temp.replace(DB)
    print(f"Restore verified. Previous database (if any) saved alongside: {DB}.before-restore")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup")
    check = commands.add_parser("verify"); check.add_argument("path", type=Path, nargs="?", default=DB)
    restore_cmd = commands.add_parser("restore"); restore_cmd.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "backup": backup()
    elif args.command == "verify":
        integrity(args.path.resolve()); print(f"Integrity check passed: {args.path.resolve()}")
    else: restore(args.path.resolve())

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"Database maintenance failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
