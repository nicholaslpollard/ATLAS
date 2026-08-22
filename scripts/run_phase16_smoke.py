from __future__ import annotations

import argparse
import json

from packages.control_plane.phase16_smoke import Phase16OperationalSmoke
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ATLAS Phase 16 loopback operational smoke validation."
    )
    parser.add_argument(
        "--refresh-brokers",
        action="store_true",
        help=(
            "Explicitly perform read-only Webull/Alpaca reconciliation. "
            "Omit this flag for the default zero-provider-call acceptance smoke."
        ),
    )
    args = parser.parse_args()
    report = Phase16OperationalSmoke(load_settings()).run(
        refresh_brokers=args.refresh_brokers,
        write_report=True,
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
