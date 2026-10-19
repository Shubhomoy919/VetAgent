"""Export, load and verify frozen results snapshots; remove demo runs.

    python -m app.scripts.snapshot export 20261019-090352-249aa9   # write snapshots/v1.0.0/run.json
    python -m app.scripts.snapshot load                            # load into the database (skips if present)
    python -m app.scripts.snapshot verify                          # re-score; exit 1 if any number differs
    python -m app.scripts.snapshot purge-demo                      # delete demo runs from the database
"""

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.snapshot import SnapshotError, export_run, load_snapshot, verify_snapshot, write_snapshot
from app.storage.db import Store


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["export", "load", "verify", "purge-demo"])
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--path", type=Path, default=None, help="snapshot file (default SNAPSHOT_PATH)")
    args = ap.parse_args(argv)
    path = args.path or get_settings().snapshot_file
    store = Store(hide_demo=False)
    try:
        if args.command == "export":
            if not args.run_id:
                ap.error("export needs a run id")
            digest = write_snapshot(export_run(store, args.run_id), path)
            print(f"Wrote {path} (sha256 {digest})")
        elif args.command == "load":
            rid = load_snapshot(store, path)
            print(f"Loaded run {rid}" if rid else "Snapshot run is already in the database; nothing to do.")
        elif args.command == "verify":
            problems = verify_snapshot(path)
            if problems:
                print("Snapshot does NOT reproduce:\n  " + "\n  ".join(problems))
                return 1
            print(f"OK: re-scoring {path.name} reproduces every metric, and the benchmark hash matches.")
        else:
            print(f"Deleted {store.delete_demo_runs()} demo run(s) and their results.")
    except (SnapshotError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
