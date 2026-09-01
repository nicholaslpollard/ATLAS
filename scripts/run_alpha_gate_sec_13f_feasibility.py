from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_feasibility import (  # noqa: E402
    SEC13FFeasibility,
    SEC_13F_FEASIBILITY_CONTRACT,
    SEC_13F_FEASIBILITY_FINGERPRINT,
    SEC_13F_MECHANISM_CANDIDATE,
)
from packages.core.settings import get_settings  # noqa: E402
from packages.providers.sec_13f_datasets import SEC13FDatasetClient  # noqa: E402


def main() -> int:
    settings = get_settings()
    print("ATLAS Pre-Phase33 — SEC Form 13F Institutional Positioning Source Feasibility")
    print(f"Feasibility contract: {SEC_13F_FEASIBILITY_CONTRACT}")
    print(f"Feasibility fingerprint: {SEC_13F_FEASIBILITY_FINGERPRINT}")
    print(f"Mechanism candidate: {SEC_13F_MECHANISM_CANDIDATE}")
    print("Economic hypotheses: NOT FROZEN")
    print("CUSIP -> ATLAS identity authority: NOT GRANTED")
    print("Full-history acquisition: DISABLED")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()
    result = SEC13FFeasibility(settings, SEC13FDatasetClient(), progress=print).run()
    print()
    print(f"SEC Form 13F feasibility: {result['status']}")
    for anchor in result["anchors"]:
        print(
            f"- {anchor['label']}: initial_HR={anchor['initial_hr_submissions']} "
            f"holdings={anchor['initial_hr_infotable_rows']} "
            f"managers={anchor['initial_hr_unique_ciks']} "
            f"valid_CUSIP={anchor['initial_hr_valid_cusip_fraction']:.6f} "
            f"orphan_rows={anchor['infotable_orphan_rows']} "
            f"duplicate_info_keys={anchor['infotable_primary_key_duplicates']}"
        )
    print(f"Calendar-year span: {result['calendar_year_span_inclusive']}")
    for name, passed in result["gates"].items():
        print(f"  {name}: {passed}")
    governance = result["governance"]
    print(f"Target outcome rows read: {governance['target_outcome_rows_read']}")
    print(f"Protected return rows read: {governance['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {governance['protected_holdout_consumed']}")
    print(f"Provider reads performed: {governance['provider_reads_performed']}")
    print(f"Phase33 Signal-to-Trade authority: {governance['phase33_signal_to_trade_authority']}")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
