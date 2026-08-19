from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.identity_probe import MLHistoricalIdentityProbe


def _pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase 10 historical ML identity coverage")
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT, "development")
    report = MLHistoricalIdentityProbe(settings).run(args.end)

    print("ATLAS Phase 10 Gate 2 Historical Identity / Eligibility Probe")
    print(f"  contract:                         {report.contract_version}")
    print(f"  history:                          {report.history_start} -> {report.history_end}")
    print("  probe status:                     EVIDENCE_ONLY")
    print(f"  liquid complete candidates:       {report.candidate_rows:,}")
    print(f"  candidate symbols:                {report.candidate_symbols:,}")
    print("  identity status rows:")
    for key, value in report.identity_status_row_counts.items():
        print(f"    {key:<31} {value:>10,}")
    print("  identity status symbols:")
    for key, value in report.identity_status_symbol_counts.items():
        print(f"    {key:<31} {value:>10,}")
    print(
        f"  identity-safe rows:               {report.identity_safe_rows:,} "
        f"({_pct(report.identity_safe_fraction)})"
    )
    print(f"  identity-safe symbols:            {report.identity_safe_symbols:,}")
    print(
        f"  structurally eligible rows:       {report.structurally_eligible_rows:,} "
        f"({_pct(report.structurally_eligible_fraction)})"
    )
    print(f"  structurally eligible symbols:    {report.structurally_eligible_symbols:,}")
    print(f"  structurally ineligible rows:     {report.structurally_ineligible_rows:,}")
    print(f"  unresolved identity rows:         {report.unresolved_rows:,}")
    print(f"  structural exclusion reasons:     {report.structural_ineligibility_reason_rows}")
    print("  annual evidence:")
    for item in report.annual_evidence:
        print(
            f"    {item.year}: candidates={item.candidate_rows:,} "
            f"identity-safe={item.identity_safe_rows:,} "
            f"eligible={item.structurally_eligible_rows:,} "
            f"unresolved={item.unresolved_rows:,} "
            f"eligible-share={_pct(item.structurally_eligible_fraction)}"
        )
    print(f"  current active filter used:        {report.current_active_filter_used}")
    print(f"  current delisted filter used:      {report.current_delisted_filter_used}")
    print(f"  current route filter used:         {report.current_route_filter_used}")
    print(f"  ticker-text splice used:           {report.ticker_text_splicing_used}")
    print("  historical identity policy:        NOT YET LOCKED")
    print("  prediction-label policy:           NOT YET LOCKED")
    print(f"  wall time:                         {report.wall_seconds:.3f}s")
    print(f"  report:                            {report.report_path}")
    print("  result:                            EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
