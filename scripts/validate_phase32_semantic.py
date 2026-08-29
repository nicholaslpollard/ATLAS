from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_V2 = "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
EXPECTED_SEMANTIC = "ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82"
EXPECTED_CONTRACT = (
    "phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes"
)
EXPECTED_SAFE_START = "2022-01-03"


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
        "packages/providers/massive/phase32_semantic.py",
        "packages/backtesting/phase32_semantic_feasibility.py",
        "scripts/run_phase32_semantic_feasibility.py",
        "tests/unit/test_phase32_semantic_feasibility.py",
    )
    sources = {path: read(path) for path in paths}
    for path, source in sources.items():
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_semantic_feasibility import (
        PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT,
        PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN,
        PHASE32_SEMANTIC_CONTRACT_VERSION,
        PHASE32_SEMANTIC_PROBE_WINDOWS,
        PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED,
        PHASE32_SEMANTIC_SAFE_HISTORY_START,
        PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED,
        phase32_semantic_feasibility_fingerprint,
    )
    from packages.providers.massive.phase32_semantic import (
        PHASE32_DISCLOSURES_ENDPOINT,
        PHASE32_DISCLOSURES_PAGE_LIMIT,
        PHASE32_TEXT_ENDPOINT,
        PHASE32_TEXT_PAGE_LIMIT,
        PHASE32_TAXONOMY_ENDPOINT,
        PHASE32_TAXONOMY_PAGE_LIMIT,
    )

    if PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT != EXPECTED_V2:
        raise AssertionError("accepted Phase32 V2 fingerprint drifted")
    if PHASE32_SEMANTIC_CONTRACT_VERSION != EXPECTED_CONTRACT:
        raise AssertionError("Phase32 semantic contract version drifted")
    if phase32_semantic_feasibility_fingerprint() != EXPECTED_SEMANTIC:
        raise AssertionError("Phase32 semantic feasibility fingerprint drifted")
    if PHASE32_SEMANTIC_SAFE_HISTORY_START != EXPECTED_SAFE_START:
        raise AssertionError("Phase32 semantic safe history start drifted")
    if len(PHASE32_SEMANTIC_PROBE_WINDOWS) != 5:
        raise AssertionError("Phase32 semantic probe-window count drifted")
    if PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("Phase32 hypotheses froze before semantic source qualification")
    if (
        PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED
        or PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED
    ):
        raise AssertionError("Phase32 semantic source gate may not read market outcomes")

    if PHASE32_DISCLOSURES_ENDPOINT != "/stocks/filings/8-K/vX/disclosures":
        raise AssertionError("Phase32 disclosures endpoint drifted")
    if PHASE32_TEXT_ENDPOINT != "/stocks/filings/8-K/vX/text":
        raise AssertionError("Phase32 8-K text endpoint drifted")
    if PHASE32_TAXONOMY_ENDPOINT != "/stocks/taxonomies/vX/disclosures":
        raise AssertionError("Phase32 taxonomy endpoint drifted")
    if (
        PHASE32_DISCLOSURES_PAGE_LIMIT != 1000
        or PHASE32_TEXT_PAGE_LIMIT != 100
        or PHASE32_TAXONOMY_PAGE_LIMIT != 1000
    ):
        raise AssertionError("Phase32 semantic source page bounds drifted")

    semantic = sources["packages/backtesting/phase32_semantic_feasibility.py"]
    adapter = sources["packages/providers/massive/phase32_semantic.py"]
    runner = sources["scripts/run_phase32_semantic_feasibility.py"]

    for token in (
        '"target_outcome_rows_read": 0',
        '"protected_candidate_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"phase33_signal_to_trade_entry_satisfied": False',
        "supporting_text_grounded_in_items_text",
        "sec_accession_form_filing_date_acceptance_reconciled",
        "taxonomy_categories_valid",
        "ticker_aligned",
        "phase32_sec_8k_semantic_feasibility",
    ):
        require(semantic, token, "semantic source contract")

    for token in (
        '"filing_date.gte"',
        '"filing_date.lte"',
        '"form_type": "8-K"',
        '"cik": cik_text.zfill(10)',
        "validate_disclosure_row",
        "validate_text_row",
        "validate_taxonomy_row",
    ):
        require(adapter, token, "semantic Massive adapter")

    for bad in (
        "ticker.upper(",
        "ticker.lower(",
        ".str.upper(",
        ".str.lower(",
        "packages.execution",
        "packages.brokers",
        ".submit_order(",
        ".place_order(",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
    ):
        forbid(semantic + "\n" + adapter, bad, "outcome/trading or ticker-normalization authority")

    require(runner, "Stop here. Diagnose and repair", "root-cause-before-workaround failure rule")
    require(runner, "Alpha hypotheses: NOT YET FROZEN", "unfrozen hypothesis boundary")
    require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "zero-outcome boundary")

    docs = "\n".join(
        read(path)
        for path in (
            "README.md",
            "docs/roadmap.md",
            "docs/current_status.md",
            "docs/phase32_sec_8k_material_event_alpha.md",
            "docs/phase32_semantic_source_qualification.md",
        )
    )
    for token in (
        EXPECTED_V2,
        EXPECTED_SEMANTIC,
        EXPECTED_SAFE_START,
        "scripts/run_phase32_semantic_feasibility.py",
    ):
        require(docs, token, "synchronized Phase32 docs")
    require(docs.lower(), "root cause", "root-cause-before-workaround documentation")

    print("ATLAS Phase 32 semantic source qualification contracts: PASS")
    print(f"- accepted V2 source fingerprint pinned: {EXPECTED_V2}")
    print(f"- semantic source fingerprint pinned: {EXPECTED_SEMANTIC}")
    print("- semantic history is conservatively frozen from 2022-01-03")
    print("- taxonomy, disclosure, text-grounding, ticker, and SEC provenance checks are mandatory")
    print("- hypotheses remain unfrozen and target/protected outcomes remain unread")
    print("- source errors stop progression for diagnosis/repair before any alternate method")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
