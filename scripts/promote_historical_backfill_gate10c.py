from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_handoff import HistoricalBackfillRegimeHandoff


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote the accepted Gate 10-C regime bundle")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="apply or resume the journaled production handoff")
    mode.add_argument("--rollback", action="store_true", help="restore the frozen pre-promotion regime files")
    args = parser.parse_args()

    handoff = HistoricalBackfillRegimeHandoff(load_settings())
    if args.rollback:
        result = handoff.rollback()
        print("ATLAS Historical Backfill Gate 10-C Production Regime Rollback")
        print(f"  handoff id:                       {result['handoff_id']}")
        print(f"  status:                           {result['status']}")
        return

    report = handoff.apply()
    print("ATLAS Historical Backfill Gate 10-C Production Regime Promotion")
    print("  safety: old current-state files are hash-frozen in rollback storage before atomic replacement")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  handoff id:                       {report['handoff_id']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print(f"  status:                           {report['status']}")
    print("  live current-state files:")
    for key, path in report["live_paths"].items():
        print(f"    {key:<28} {path}")
    print("  frozen rollback files:")
    for key, path in report["rollback_paths"].items():
        print(f"    {key:<28} {path}")
    print("  production history:")
    for key, entry in report["history_plan"].items():
        print(f"    {key:<20} {entry['target_path']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  journal:                          {report['journal_path']}")
    print(f"  report:                           {report['report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-C production regime promotion: FAIL")
    print("  Historical Backfill Gate 10-C journaled production promotion: PASS")
    print("  Historical Backfill Gate 10-C post-promotion independent validation: CURRENT")


if __name__ == "__main__":
    main()
