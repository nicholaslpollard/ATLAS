from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_SEMANTIC_V2 = "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
EXPECTED_CENSUS_VERSION = "phase32-semantic-v2-source-census-v1-no-market-outcomes"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    paths = (
        "packages/backtesting/phase32_semantic_source_census.py",
        "scripts/run_phase32_semantic_v2_source_census.py",
        "tests/unit/test_phase32_semantic_source_census.py",
    )
    sources = {path: read(path) for path in paths}
    for path, source in sources.items():
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_semantic_source_census import (
        PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT,
        PHASE32_SEMANTIC_V2_SOURCE_CENSUS_VERSION,
    )

    if PHASE32_SEMANTIC_V2_ACCEPTED_FINGERPRINT != EXPECTED_SEMANTIC_V2:
        raise AssertionError("accepted semantic V2 fingerprint drifted")
    if PHASE32_SEMANTIC_V2_SOURCE_CENSUS_VERSION != EXPECTED_CENSUS_VERSION:
        raise AssertionError("semantic V2 source census version drifted")

    census = sources["packages/backtesting/phase32_semantic_source_census.py"]
    runner = sources["scripts/run_phase32_semantic_v2_source_census.py"]

    for token in (
        '"target_outcome_rows_read": 0',
        '"protected_candidate_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"network_calls": 0',
        '"provider_writes": 0',
        '"broker_reads": 0',
        '"broker_writes": 0',
        '"orders": 0',
        '"paper_submits": 0',
        '"live_writes": 0',
        'sha256_file(taxonomy_path)',
        'sha256_file(path)',
    ):
        require(census, token, "local source-only census invariant")

    for bad in (
        "packages.providers",
        "requests.",
        "urllib.request",
        "httpx",
        "duckdb",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
        "market_bars",
        "price_history",
        ".submit_order(",
        ".place_order(",
        "packages.execution",
        "packages.brokers",
    ):
        forbid(census + "\n" + runner, bad, "network/outcome/trading authority")

    for token in (
        "Network/provider calls: NONE",
        "Market outcomes: FORBIDDEN / UNREAD",
        "freeze a finite hypothesis family",
        "Stop here. Repair the source-evidence/census defect",
        "FULL TAXONOMY WITH PROBE-WINDOW COUNTS",
    ):
        require(runner, token, "census runner contract")

    docs = "\n".join(
        read(path)
        for path in (
            "README.md",
            "docs/current_status.md",
            "docs/roadmap.md",
            "docs/phase32_sec_8k_material_event_alpha.md",
            "docs/phase32_semantic_source_qualification.md",
        )
    )
    for token in (
        EXPECTED_SEMANTIC_V2,
        "Semantic V2 — ACCEPTED PASS",
        "scripts/run_phase32_semantic_v2_source_census.py",
        "zero network calls",
        "No development return",
    ):
        require(docs, token, "synchronized Phase32 post-semantic-V2 state")

    print("ATLAS Phase 32 semantic V2 source census contracts: PASS")
    print(f"- accepted semantic V2 fingerprint pinned: {EXPECTED_SEMANTIC_V2}")
    print(f"- source census contract pinned: {EXPECTED_CENSUS_VERSION}")
    print("- census reads immutable local source evidence only and hash-checks retained artifacts")
    print("- network/provider calls and market-outcome reads remain forbidden")
    print("- hypothesis family remains unfrozen until census evidence is reviewed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
