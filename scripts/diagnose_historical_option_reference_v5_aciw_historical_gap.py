from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_option_reference_v5_aciw_historical_gap_diagnostic import (
    HISTORICAL_OPTION_REFERENCE_V5_ACIW_HISTORICAL_GAP_DIAGNOSTIC_FINGERPRINT,
    TARGET_PARTITION,
    TARGET_TICKER,
    run_historical_option_reference_v5_aciw_historical_gap_diagnostic,
)


def _first_attempt(section: dict[str, object]) -> dict[str, object]:
    attempts = section.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return {}
    first = attempts[0]
    return dict(first) if isinstance(first, dict) else {}


def main() -> int:
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical Option Reference V5 ACIW Historical-Gap Diagnostic")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_OPTION_REFERENCE_V5_ACIW_HISTORICAL_GAP_DIAGNOSTIC_FINGERPRINT}"
    )
    print(f"  target partition: {TARGET_PARTITION}")
    print(f"  target ticker: {TARGET_TICKER}")
    print("  provider writes: disabled")
    print("  bulk acquisition: disabled")
    print("  conflict-resolution authority: none")
    print("  quarantine authority: none")
    print("  strategy/PAPER/LIVE authority: none")

    report = run_historical_option_reference_v5_aciw_historical_gap_diagnostic(
        settings
    )

    current = dict(report["current_structural_list"])
    current_first = _first_attempt(current)
    interpretation = dict(report["interpretation"])
    matrix = list(interpretation["historical_matrix"])

    print(
        "\nHISTORICAL OPTION REFERENCE V5 ACIW HISTORICAL-GAP "
        "DIAGNOSTIC: COMPLETE"
    )
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  current structural-list: "
        f"target_rows={int(current_first.get('target_row_count', 0))} "
        f"candidates={int(current_first.get('candidate_row_count', 0))} "
        f"pages={int(current_first.get('page_count', 0))} "
        f"stable={current.get('stable')}"
    )
    print(
        "  current conflicting fields: "
        + json.dumps(
            interpretation.get("current_conflicting_fields", {}),
            sort_keys=True,
        )
    )
    print(
        "  current underlying tickers: "
        + json.dumps(
            interpretation.get("current_underlying_tickers", []),
            sort_keys=True,
        )
    )
    print(
        "  current primary exchanges: "
        + json.dumps(
            interpretation.get("current_primary_exchanges", []),
            sort_keys=True,
        )
    )
    print(
        "  current correction values JSON: "
        + json.dumps(
            interpretation.get("current_correction_values_json", []),
            sort_keys=True,
        )
    )
    print("  historical boundary matrix:")
    for item in matrix:
        print(
            "    "
            f"as_of={item['as_of']} "
            f"expired={item['expired']} "
            f"target_rows={item['target_row_count']} "
            f"list_stable={item['list_stable']} "
            f"overview_present={item['overview_present']} "
            f"overview_stable={item['overview_stable']} "
            f"list_overview_match={item['list_overview_exact_match']} "
            f"current_exact_matches={item['historical_payload_current_exact_match_count']}"
        )
    print(
        "  V5 pre-expiration zero-target failure reproduced: "
        + str(
            interpretation[
                "v5_preexpiration_zero_target_failure_reproduced"
            ]
        )
    )
    print(
        "  any historical exact list/overview/current match: "
        + str(interpretation["any_historical_exact_match"])
    )
    print(
        "  exact historical matches: "
        + json.dumps(
            interpretation[
                "historical_exact_list_overview_current_matches"
            ],
            sort_keys=True,
        )
    )
    print(
        "  manifest: "
        + str(
            PROJECT_ROOT
            / "data/options/manifests/massive/"
            "historical_option_reference_v5_aciw_historical_gap_diagnostic.json"
        )
    )
    print(
        "  authority: diagnostic only; no V5/V6 resolution or quarantine "
        "rule is authorized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
