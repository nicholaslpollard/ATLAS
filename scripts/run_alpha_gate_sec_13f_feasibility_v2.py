from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_feasibility import SEC_13F_MECHANISM_CANDIDATE  # noqa: E402
from packages.backtesting.alpha_gate_sec_13f_feasibility_v2 import (  # noqa: E402
    SEC13FFeasibilityV2,
    SEC_13F_CAPACITY_EVIDENCE_KIND,
    SEC_13F_FEASIBILITY_SCOPE,
    SEC_13F_FEASIBILITY_V2_CONTRACT,
    SEC_13F_FEASIBILITY_V2_FINGERPRINT,
)
from packages.core.settings import get_settings  # noqa: E402
from packages.providers.sec_13f_datasets import SEC13FDatasetClient  # noqa: E402


def main() -> int:
    settings = get_settings()
    print("ATLAS Pre-Phase33 — SEC Form 13F Institutional Positioning Gate0 V2")
    print(f"Feasibility contract: {SEC_13F_FEASIBILITY_V2_CONTRACT}")
    print(f"Feasibility fingerprint: {SEC_13F_FEASIBILITY_V2_FINGERPRINT}")
    print(f"Mechanism candidate: {SEC_13F_MECHANISM_CANDIDATE}")
    print(f"Population scope: {SEC_13F_FEASIBILITY_SCOPE}")
    print(f"Capacity evidence: {SEC_13F_CAPACITY_EVIDENCE_KIND}")
    print("Complete source scope: NOT PROVEN BY THIS PROBE")
    print("Scientific freeze authority: NOT GRANTED")
    print("Economic hypotheses: NOT FROZEN")
    print("CUSIP -> ATLAS identity authority: NOT GRANTED")
    print("Full-history acquisition: DISABLED")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()
    result = SEC13FFeasibilityV2(settings, SEC13FDatasetClient(), progress=print).run()
    print()
    print(f"SEC Form 13F bounded probe: {result['status']}")
    for anchor in result["anchors"]:
        print(f"- {anchor['label']}: initial_HR={anchor['initial_hr_submissions']} holdings={anchor['initial_hr_infotable_rows']} managers={anchor['initial_hr_unique_ciks']} valid_CUSIP={anchor['initial_hr_valid_cusip_fraction']:.6f} orphan_rows={anchor['infotable_orphan_rows']} duplicate_info_keys={anchor['infotable_primary_key_duplicates']}")
    print(f"Calendar-year span: {result['calendar_year_span_inclusive']}")
    for name, passed in result["structural_gates"].items():
        print(f"  {name}: {passed}")
    population = result["population_coverage"]
    print(f"Population scope proven complete: {population['source_scope_proven']}")
    print(f"Capacity evidence complete: {result['capacity_evidence_complete']}")
    print(f"Scientific freeze allowed: {result['scientific_freeze_allowed']}")
    governance = result["governance"]
    print(f"Target outcome rows read: {governance['target_outcome_rows_read']}")
    print(f"Protected return rows read: {governance['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {governance['protected_holdout_consumed']}")
    print(f"Provider reads performed: {governance['provider_reads_performed']}")
    print(f"Phase33 Signal-to-Trade authority: {governance['phase33_signal_to_trade_authority']}")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
