from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase29_closeout import (
    PHASE29_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE29_CLOSEOUT_REPORT_CONTRACT_VERSION,
    phase29_architecture_audit_checks,
)


def main() -> None:
    checks = phase29_architecture_audit_checks(PROJECT_ROOT)
    print(f"Phase 29 closeout contract: {PHASE29_CLOSEOUT_REPORT_CONTRACT_VERSION}")
    print(f"Phase 29 anti-workaround audit contract: {PHASE29_ARCHITECTURE_AUDIT_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 29 closeout contract validation failed: " + ", ".join(failed))
    print("Phase 29 closeout and anti-workaround contracts: PASS")


if __name__ == "__main__":
    main()
