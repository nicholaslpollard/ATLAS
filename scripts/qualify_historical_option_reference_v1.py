from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_option_reference_qualification import (
    HISTORICAL_OPTION_REFERENCE_QUALIFICATION_FINGERPRINT,
    run_historical_option_reference_qualification,
)


def main() -> int:
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical Option Reference Source Qualification")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_OPTION_REFERENCE_QUALIFICATION_FINGERPRINT}"
    )
    print("  provider: Massive")
    print("  endpoint: /v3/reference/options/contracts")
    print("  bulk downloads: disabled")
    print("  provider writes: disabled")
    print("  strategy/PAPER/LIVE authority: none")

    report = run_historical_option_reference_qualification(settings)

    print(f"\nHISTORICAL OPTION REFERENCE QUALIFICATION: {report['status']}")
    for probe in report["probes"]:
        first = probe["first_page"]
        print(
            f"  {probe['name']}: http={probe['http_status']} "
            f"rows={int(first['result_count']):,} "
            f"distinct_tickers={int(first['distinct_nonempty_tickers']):,} "
            f"next_url={probe['next_url_present']}"
        )
        repeat = probe.get("repeat_first_page")
        if isinstance(repeat, dict):
            print(
                "    repeat stability: "
                f"{repeat['stable']} "
                f"fingerprint={repeat['results_fingerprint']}"
            )
        second = probe.get("second_page")
        if isinstance(second, dict):
            print(
                "    second page: "
                f"rows={int(second['result_count']):,} "
                f"overlap={int(second['ticker_overlap_with_first_page']):,} "
                f"next_url={second['next_url_present']}"
            )
        if first["missing_required_fields"]:
            print(
                "    missing required fields: "
                f"{first['missing_required_fields']}"
            )
        if first["unknown_fields"]:
            print(f"    additive fields observed: {first['unknown_fields']}")

    print("\n  Qualification dimensions:")
    for item in report["dimensions"]:
        print(f"    {item['name']}: {item['status']}")
        print(f"      {item['evidence']}")

    print(f"\n  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        "  manifest: "
        + str(
            PROJECT_ROOT
            / "data/options/manifests/"
            "historical_option_reference_qualification_v1.json"
        )
    )
    print(
        "  source role: reference identity/structure only; "
        "no historical candidate-availability or dynamic-deliverable authority"
    )
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
