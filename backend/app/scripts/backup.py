"""Back up the database and the editable data files, keeping the newest N backups.

    python -m app.scripts.backup                 # writes DATA_DIR/backups/<timestamp>/
    python -m app.scripts.backup --keep 14 --dest /some/other/disk

Uses SQLite's online backup API, so it is safe while the server is running. In Docker:
    docker compose exec vetagentbench python -m app.scripts.backup
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATA_DIR

FILES = ("cases.json", "drug_table.csv", "knowledge_seed.json", "settings.json")


def backup(dest_root: Path, keep: int) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest = dest_root / stamp
    dest.mkdir(parents=True, exist_ok=False)
    db = DATA_DIR / "runs.db"
    if db.is_file():
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        out = sqlite3.connect(dest / "runs.db")
        with out:
            src.backup(out)
        src.close()
        out.close()
        check = sqlite3.connect(dest / "runs.db")
        ok = check.execute("PRAGMA integrity_check").fetchone()[0]
        check.close()
        if ok != "ok":
            raise RuntimeError(f"backup integrity check failed: {ok}")
    for name in FILES:
        if (DATA_DIR / name).is_file():
            shutil.copy2(DATA_DIR / name, dest / name)
    old = sorted((p for p in dest_root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for p in old[:-keep] if keep > 0 else []:
        shutil.rmtree(p)
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, default=DATA_DIR / "backups")
    ap.add_argument("--keep", type=int, default=14)
    args = ap.parse_args(argv)
    try:
        dest = backup(args.dest, args.keep)
    except (OSError, sqlite3.Error, RuntimeError) as e:
        print(f"Backup failed: {e}", file=sys.stderr)
        return 1
    print(f"Backup written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
