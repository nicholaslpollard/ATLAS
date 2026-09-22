from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_option_reference_v4_correction_conflict_diagnostic import (
    HISTORICAL_OPTION_REFERENCE_V4_CORRECTION_CONFLICT_DIAGNOSTIC_FINGERPRINT,
    TARGET_PARTITION,
    TARGET_TICKER,
    run_historical_option_reference_v4_correction_conflict_diagnostic,
)


def _first_attempt(section: dict[str, object]) -> dict[str, object]:
    attempts = section.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return {}
    first = attempts[0]
    return dict(first) if isinstance(first, dict) else {}


def main() -> int:
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical Option Reference V4 Correction Conflict Diagnostic")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_OPTION_REFERENCE_V4_CORRECTION_CONFLICT_DIAGNOSTIC_FINGERPRINT}"
    )
    print(f"  target partition: {TARGET_PARTITION}")
    print(f"  target ticker: {TARGET_TICKER}")
    print("  provider writes: disabled")
    print("  bulk acquisition: disabled")
    print("  conflict-resolution authority: none")
    print("  strategy/PAPER/LIVE authority: none")

    report = run_historical_option_reference_v4_correction_conflict_diagnostic(
        settings
    )

    current_list = dict(report["current_structural_list"])
    historical_list = dict(report["historical_structural_list"])
    current_overview = dict(report["current_contract_overview"])
    historical_overview = dict(report["historical_contract_overview"])
    interpretation = dict(report["interpretation"])

    current_first = _first_attempt(current_list)
    historical_first = _first_attempt(historical_list)
    current_overview_first = _first_attempt(current_overview)
    historical_overview_first = _first_attempt(historical_overview)

    print(
        "\nHISTORICAL OPTION REFERENCE V4 CORRECTION CONFLICT "
        "DIAGNOSTIC: COMPLETE"
    )
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  current structural-list: "
        f"target_rows={int(current_first.get('target_row_count', 0))} "
        f"candidates={int(current_first.get('candidate_row_count', 0))} "
        f"stable={current_list.get('stable')}"
    )
    print(
        "  historical structural-list: "
        f"target_rows={int(historical_first.get('target_row_count', 0))} "
        f"candidates={int(historical_first.get('candidate_row_count', 0))} "
        f"stable={historical_list.get('stable')}"
    )
    print(
        "  current target correction values: "
        + json.dumps(current_first.get("target_correction_values", []), sort_keys=True)
    )
    print(
        "  historical target correction values: "
        + json.dumps(
            historical_first.get("target_correction_values", []),
            sort_keys=True,
        )
    )
    print(
        "  current conflicting fields: "
        + json.dumps(current_list.get("field_differences", {}), sort_keys=True)
    )
    print(
        "  historical conflicting fields: "
        + json.dumps(historical_list.get("field_differences", {}), sort_keys=True)
    )
    print(
        "  current contract overview: "
        f"status={current_overview_first.get('http_status')} "
        f"present={current_overview_first.get('row_present')} "
        f"not_found={current_overview_first.get('not_found')} "
        f"stable={current_overview.get('stable')}"
    )
    print(
        "  historical contract overview: "
        f"status={historical_overview_first.get('http_status')} "
        f"present={historical_overview_first.get('row_present')} "
        f"not_found={historical_overview_first.get('not_found')} "
        f"stable={historical_overview.get('stable')}"
    )
    print("  interpretation:")
    for key, value in interpretation.items():
        print(f"    {key}: {json.dumps(value, sort_keys=True, default=str)}")

    print(
        "  manifest: "
        + str(
            PROJECT_ROOT
            / "data/options/manifests/massive/"
            "historical_option_reference_v4_correction_conflict_diagnostic.json"
        )
    )
    print(
        "  authority: diagnostic only; no V4/V5 conflict-resolution rule is authorized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
