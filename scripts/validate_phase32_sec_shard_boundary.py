from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import (
    SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS,
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    _select_declared_shard_candidates,
)


CONTRACT = "phase32-sec-submissions-declared-shard-rollover-boundary-v1"
TARGET_DATE = "2023-10-05"


def _item(name: str, start: str, end: str) -> dict[str, str]:
    return {"name": name, "filingFrom": start, "filingTo": end}


def main() -> int:
    failures: list[str] = []

    if SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS != 1:
        failures.append("declared-shard boundary tolerance must remain exactly one calendar day")
    if SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP != 2:
        failures.append("archive shard lookup hard bound must remain exactly two")

    covering = _item(
        "CIK0001564708-submissions-002.json", "2023-10-05", "2023-10-05"
    )
    adjacent = _item(
        "CIK0001564708-submissions-001.json", "2012-12-21", "2023-10-04"
    )
    distant = _item(
        "CIK0001564708-submissions-003.json", "2012-12-21", "2023-10-03"
    )

    selected = _select_declared_shard_candidates([covering, adjacent], filing_date=TARGET_DATE)
    if selected != (covering,):
        failures.append("date-covering SEC-declared shard must outrank and suppress adjacent fallback")

    selected = _select_declared_shard_candidates([adjacent], filing_date=TARGET_DATE)
    if selected != (adjacent,):
        failures.append("one-day adjacent SEC-declared shard must be eligible only when coverage is absent")

    selected = _select_declared_shard_candidates([distant], filing_date=TARGET_DATE)
    if selected:
        failures.append("a shard more than one day away must remain ineligible")

    three_adjacent = [
        _item(
            f"CIK0001564708-submissions-{index:03d}.json",
            "2012-12-21",
            "2023-10-04",
        )
        for index in range(1, 4)
    ]
    try:
        _select_declared_shard_candidates(three_adjacent, filing_date=TARGET_DATE)
    except ProviderError:
        pass
    else:
        failures.append("more than two eligible SEC-declared shards must fail closed")

    print("ATLAS Phase 32 SEC submissions shard-boundary contract")
    print(f"Contract: {CONTRACT}")
    print(f"Boundary tolerance: {SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS} calendar day")
    print(f"Maximum SEC-declared shard reads per lookup: {SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP}")
    print("Fallback scope: SEC-declared shard names only; no guessed URLs")
    print("Exact accession + requested filing date + original 8-K validation remains mandatory after read")
    print("Stock/SPY/options outcomes / broker / orders / PAPER / LIVE: absent")

    if failures:
        print("Result: NOT ACCEPTED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Result: PASS")
    print("- exact date coverage remains primary")
    print("- one-day adjacent fallback is allowed only when no date-covering shard is declared")
    print("- more distant shards remain forbidden")
    print("- the existing two-shard hard bound remains fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
