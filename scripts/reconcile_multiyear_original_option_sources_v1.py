from __future__ import annotations

"""Read-only original 2022/2025 option-source identity reconciliation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_original_option_source_crosswalk_v1 import (
    OriginalCrosswalkError, build_original_source_crosswalk,
)


def main() -> int:
    print("ATLAS Multi-Year Original 2022 + 2025 Options Source Crosswalk / OFFLINE", flush=True)
    print("  Zero provider requests; original 2022/2025 source and receipt evidence reused.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        result, path, action = build_original_source_crosswalk(
            settings, progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            )
        )
        print(f"  result: {action} / {path}", flush=True)
        print(f"  original stock case denominator: {result['case_denominator']}", flush=True)
        print(f"  original 2022 reconciled: {result['2022_total_original_cases_reconciled']}", flush=True)
        print(f"  original 2022 unmatched: {result['2022_unmatched_cases_remaining']}", flush=True)
        print(f"  original 2022 additive representatives: {result['2022_original_additive_representatives']}", flush=True)
        print(f"  original 2022 same-key members: {result['2022_original_additive_same_key_members']}", flush=True)
        print(f"  old-source only members, excluded from accepted case denominator: {result['2022_prior_only_same_key_member_count']}", flush=True)
        for member in result["2022_prior_only_same_key_members"]:
            print(f"    prior-only ID={member['case_id']} original_key={member['source_key']} representative={member['representative_id']} shard={member['shard_index']}", flush=True)
        print(f"  original 2022 no-CALL/exact-query abstentions: {result['2022_original_additive_source_abstentions']}", flush=True)
        print(f"  original 2022 pilot representatives: {result['2022_original_pilot_representatives']}", flush=True)
        print(f"  original 2022 pilot other same-key cases: {result['2022_pilot_same_key_other_cases']}", flush=True)
        print(f"  original 2025 pilot overlap: {result['2025_original_pilot_matched_cases']}", flush=True)
        print(f"  original 2025 pilot dispositions: {result['2025_original_pilot_source_statuses']}", flush=True)
        for year, statuses in result["by_year"].items():
            print(f"  {year}: {statuses}", flush=True)
        print(f"  fingerprint: {result['crosswalk_fingerprint']}", flush=True)
        print("  No paid source or quote plan is authorized by this reconciliation.", flush=True)
        return 0
    except (OriginalCrosswalkError, OSError, ValueError, TypeError, KeyError,
            RuntimeError) as exc:
        print(f"ORIGINAL OPTION SOURCE CROSSWALK STOPPED: {type(exc).__name__}: {exc}",
              flush=True)
        print("  Preserve all original files. No paid retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
