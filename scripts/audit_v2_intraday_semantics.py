from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.data.b34_intraday_readiness import (
    run_b34_source_readiness,
    write_b34_source_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the finite B34 V2 minute/intraday source-readiness audit and frozen "
            "opening/premarket contract check. This is read-only with respect to providers and brokers."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="ATLAS repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the audit only; do not persist the local JSON evidence file.",
    )
    args = parser.parse_args()

    report = run_b34_source_readiness(args.project_root)
    if not args.no_write:
        path = write_b34_source_readiness(args.project_root, report)
        print(f"B34 evidence: {path}")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if bool(report.get("accepted")) else 2


if __name__ == "__main__":
    sys.exit(main())
