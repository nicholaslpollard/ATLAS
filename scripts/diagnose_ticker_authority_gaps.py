from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_authority_gap_probe import TickerAuthorityGapProbe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose cached authoritative ticker-event files that still lack a current interval."
    )
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = TickerAuthorityGapProbe(load_settings(PROJECT_ROOT)).run(args.as_of)
    print("ATLAS Phase 9 Ticker Authority Gap Diagnostic")
    print(f"  contract:                       {report.contract_version}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  probe status:                   {report.probe_status}")
    print(f"  cached unresolved instruments: {report.cached_unresolved_count}")
    print("  reason counts:")
    if not report.reason_counts:
        print("    (none)")
    else:
        for reason, count in report.reason_counts.items():
            print(f"    {reason:<38} {count:>5}")
    print("  gaps:")
    if not report.gaps:
        print("    (none)")
    else:
        for gap in report.gaps:
            print(
                f"    {gap['ticker']:<12} reason={gap['reason']} "
                f"aliases={gap['alias_count']} reuse_ids={gap['reuse_identity_count']} "
                f"figi={gap['composite_figi']}"
            )
            events = gap["events"]
            if not events:
                print("      timeline: (no authoritative events)")
            else:
                for event in events:
                    print(f"      {event['event_date']}  {event['ticker']}")
    print(f"  wall time:                      {report.wall_seconds:.3f}s")
    print(f"  report:                         {Path(report.report_path).resolve()}")
    print("  network calls:                  NONE")
    print("  result:                         EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
