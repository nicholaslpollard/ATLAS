from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_semantic_source_census import (
    PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT,
    Phase32SemanticSourceCensusError,
    build_phase32_semantic_v2_source_census,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 32 — Semantic V2 Source/Taxonomy Census")
    print(f"Accepted semantic V2 fingerprint: {PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT}")
    print("Scope: immutable accepted V2 source evidence only")
    print("Network/provider calls: NONE")
    print("Market outcomes: FORBIDDEN / UNREAD")
    print("Purpose: freeze a finite hypothesis family from source semantics before any return read")
    print()

    try:
        census = build_phase32_semantic_v2_source_census(load_settings())
    except Phase32SemanticSourceCensusError as exc:
        print("Phase 32 semantic V2 source census: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Stop here. Repair the source-evidence/census defect before freezing hypotheses.")
        return 1

    print("Phase 32 semantic V2 source census: PASS")
    print(
        "Totals: taxonomy_rows=%s observed_taxonomy_rows=%s disclosures=%s unique_accessions=%s unique_ciks=%s"
        % (
            census["taxonomy_rows"],
            census["observed_taxonomy_rows"],
            census["total_disclosure_rows"],
            census["unique_accessions"],
            census["unique_ciks"],
        )
    )
    print(
        "Ticker mapping rows: mapped=%s unmapped=%s"
        % (census["ticker_mapped_rows"], census["ticker_unmapped_rows"])
    )
    print("Target/protected outcome rows read: 0 / 0")

    print("\nWINDOWS")
    for row in census["windows"]:
        print(
            "  %s: rows=%s accessions=%s ciks=%s mapped=%s unmapped=%s"
            % (
                row["label"],
                row["disclosure_rows"],
                row["unique_accessions"],
                row["unique_ciks"],
                row["ticker_mapped_rows"],
                row["ticker_unmapped_rows"],
            )
        )

    print("\nPRIMARY CATEGORIES")
    for row in census["primary_categories"]:
        print(
            "  %s | rows=%s accessions=%s ciks=%s windows=%s"
            % (
                row["category"][0],
                row["disclosure_rows"],
                row["unique_accessions"],
                row["unique_ciks"],
                ",".join(row["windows_present"]),
            )
        )

    print("\nSECONDARY CATEGORIES")
    for row in census["secondary_categories"]:
        print(
            "  %s/%s | rows=%s accessions=%s ciks=%s windows=%s"
            % (
                row["category"][0],
                row["category"][1],
                row["disclosure_rows"],
                row["unique_accessions"],
                row["unique_ciks"],
                ",".join(row["windows_present"]),
            )
        )

    print("\nFULL TAXONOMY WITH PROBE-WINDOW COUNTS")
    for row in census["taxonomy_categories"]:
        print(
            "  %s/%s/%s | rows=%s accessions=%s ciks=%s windows=%s"
            % (
                row["primary_category"],
                row["secondary_category"],
                row["tertiary_category"],
                row["observed_disclosure_rows"],
                row["observed_unique_accessions"],
                row["observed_unique_ciks"],
                ",".join(row["observed_windows"]) or "NONE",
            )
        )
        if row["description"]:
            print(f"    description={row['description']}")

    print()
    print(f"Census report: {census['report_path']}")
    print("Next action after this PASS: freeze the finite hypothesis family and complete scientific contract; do not read returns yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
