from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.reuse_audit import MLTickerReuseAudit


def _pct(part: int, whole: int) -> float:
    return 0.0 if whole <= 0 else 100.0 * part / whole


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase 10 unresolved ticker-reuse composition")
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT, "development")
    report = MLTickerReuseAudit(settings).run(args.end)

    print("ATLAS Phase 10 Gate 2 Ticker Reuse Composition Audit")
    print(f"  contract:                              {report.contract_version}")
    print(f"  history end:                           {report.history_end}")
    print("  audit status:                          EVIDENCE_ONLY")
    print(f"  unresolved reuse rows:                 {report.unresolved_reuse_rows:,}")
    print(f"  unresolved reuse symbols:              {report.unresolved_reuse_symbols:,}")
    print(f"  max observed IDs per ticker:           {report.observed_identity_count_max:,}")
    print(f"  max stable IDs per ticker:             {report.stable_identity_count_max:,}")
    print("  reuse composition:")
    for item in report.composition:
        print(
            f"    {item.category:<26} rows={item.candidate_rows:,} "
            f"({_pct(item.candidate_rows, report.unresolved_reuse_rows):.2f}%) "
            f"symbols={item.candidate_symbols:,} "
            f"single-current-stable-ref={item.current_single_stable_reference_symbols:,} "
            f"current-composite-figi={item.current_composite_figi_symbols:,} "
            f"any-authority-interval={item.any_authoritative_interval_symbols:,}"
        )
    print(f"  one-stable+weak rows:                   {report.one_stable_plus_weak_rows:,}")
    print(f"  one-stable+weak symbols:                {report.one_stable_plus_weak_symbols:,}")
    print(
        "  one-stable+weak current FIGI symbols:   "
        f"{report.one_stable_plus_weak_current_composite_figi_symbols:,}"
    )
    print(
        "  one-stable+weak with any authority:     "
        f"{report.one_stable_plus_weak_any_authoritative_interval_symbols:,}"
    )
    print(f"  multi-stable rows/symbols:              {report.multi_stable_rows:,} / {report.multi_stable_symbols:,}")
    print(f"  weak-only rows/symbols:                 {report.weak_only_rows:,} / {report.weak_only_symbols:,}")
    print(f"  reuse symbols with current FIGI:        {report.current_composite_figi_reuse_symbols:,}")
    print(f"  reuse symbols with any authority:       {report.any_authoritative_interval_reuse_symbols:,}")
    print(f"  recoverable without dated authority:    {report.recoverable_without_date_bounded_authority}")
    print(f"  ticker-text splicing allowed:           {report.ticker_text_splicing_allowed}")
    print("  Gate 2 policy:                          NOT YET LOCKED")
    print(f"  wall time:                              {report.wall_seconds:.3f}s")
    print(f"  report:                                 {report.report_path}")
    print("  result:                                 EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
