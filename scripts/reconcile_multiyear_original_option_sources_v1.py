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
        print(f"  original 2022 cases accounted: {result['2022_total_original_cases_reconciled']}", flush=True)
        print(f"  original 2022 exact source membership gaps: {result['2022_unmatched_cases_remaining']}", flush=True)
        for case in result["2022_unmatched_original_source_cases"]:
            print(f"    uncovered ID={case['case_id']} ticker={case['ticker']} snapshot={case['signal_session']} expiry={case['expiration']} status={case['classification']} prior_key_representatives={case['same_key_existing_physical_representatives']}",flush=True)
        print(f"  original 2022 source-only additive representatives outside frozen case census: {len(result['2022_source_only_original_additive_representatives'])}",flush=True)
        for item in result["2022_source_only_original_additive_representatives"]:
            print(f"    old-only representative ID={item['case_id']} original_key={item['source_key']} shard={item['shard_index']}",flush=True)
        print(f"  original 2022 source-only pilot representatives outside frozen case census: {len(result['2022_source_only_original_pilot_representatives'])}",flush=True)
        print(f"  original 2022 pilot-key overlaps: {result['2022_pilot_same_key_other_cases']} IDs={result['2022_pilot_same_key_other_case_ids']}",flush=True)
        print(f"  original 2022 additive representatives: {result['2022_original_additive_representatives']}", flush=True)
        print(f"  original 2022 same-key members: {result['2022_original_additive_same_key_members']}", flush=True)
        print(f"  original 2022 accepted gap-linked same-key members: {result['2022_gap_linked_same_key_member_count']}", flush=True)
        for member in result["2022_gap_linked_same_key_members"]:
            print(f"    gap-linked ID={member['case_id']} original_key={member['source_key']} representative={member['representative_id']} gap={member['representative_source_gap']} shard={member['shard_index']}", flush=True)
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
