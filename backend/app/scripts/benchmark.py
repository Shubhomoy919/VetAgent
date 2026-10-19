"""Show the benchmark version and content hash, or check it against the frozen manifest.

    python -m app.scripts.benchmark                  # the data in the database: version, hash, counts
    python -m app.scripts.benchmark --files          # the seed files data/cases.json and data/drug_table.csv
    python -m app.scripts.benchmark --check [--files]  # exit 1 if the data differs from frozen v1.0.0
"""

import argparse
import json
import sys

from app.data.benchmark import benchmark_info, file_benchmark_info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--files", action="store_true", help="check the seed files instead of the database")
    args = ap.parse_args(argv)
    info = file_benchmark_info() if args.files else benchmark_info()
    print(json.dumps(info, indent=2))
    if args.check and not info["frozen"]:
        print(f"Data differs from frozen v{info['frozen_version']}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
