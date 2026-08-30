from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CORE_V2 = "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
EXPECTED_REJECTED_V1 = "ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82"
EXPECTED_SEMANTIC_V2 = "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
EXPECTED_CONTRACT = "phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes"
EXPECTED_RESEARCH_START = "2021-08-16"


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
        "packages/backtesting/phase32_semantic_feasibility_v2.py",
        "scripts/run_phase32_semantic_feasibility_v2.py",
        "tests/unit/test_phase32_semantic_feasibility_v2.py",
    )
    sources = {path: read(path) for path in paths}
    for path, source in sources.items():
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_semantic_feasibility_v2 import (
        PHASE32_ACCEPTED_CORE_V2_FINGERPRINT,
        PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT,
        PHASE32_SEMANTIC_V2_ALPHA_HYPOTHESES_FROZEN,
        PHASE32_SEMANTIC_V2_CONTRACT_VERSION,
        PHASE32_SEMANTIC_V2_PROBE_WINDOWS,
        PHASE32_SEMANTIC_V2_PROTECTED_OUTCOME_READS_ALLOWED,
        PHASE32_SEMANTIC_V2_RESEARCH_START,
        PHASE32_SEMANTIC_V2_SUPPORT_RULE,
        PHASE32_SEMANTIC_V2_TARGET_OUTCOME_READS_ALLOWED,
        PHASE32_SEMANTIC_V2_TICKER_RULE,
        phase32_semantic_v2_fingerprint,
    )

    if PHASE32_ACCEPTED_CORE_V2_FINGERPRINT != EXPECTED_CORE_V2:
        raise AssertionError("accepted Phase32 core V2 fingerprint drifted")
    if PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT != EXPECTED_REJECTED_V1:
        raise AssertionError("rejected semantic V1 fingerprint drifted")
    if PHASE32_SEMANTIC_V2_CONTRACT_VERSION != EXPECTED_CONTRACT:
        raise AssertionError("semantic V2 contract version drifted")
    if phase32_semantic_v2_fingerprint() != EXPECTED_SEMANTIC_V2:
        raise AssertionError("semantic V2 fingerprint drifted")
    if PHASE32_SEMANTIC_V2_RESEARCH_START != EXPECTED_RESEARCH_START:
        raise AssertionError("semantic V2 research boundary drifted")
    if len(PHASE32_SEMANTIC_V2_PROBE_WINDOWS) != 5:
        raise AssertionError("semantic V2 probe-window count drifted")
    if PHASE32_SEMANTIC_V2_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("Phase32 hypotheses froze before semantic V2 qualification")
    if (
        PHASE32_SEMANTIC_V2_TARGET_OUTCOME_READS_ALLOWED
        or PHASE32_SEMANTIC_V2_PROTECTED_OUTCOME_READS_ALLOWED
    ):
        raise AssertionError("semantic V2 may not read market outcomes")

    if "MAPPING_METADATA_ONLY_NOT_IDENTITY" not in PHASE32_SEMANTIC_V2_TICKER_RULE:
        raise AssertionError("semantic V2 ticker mapping rule drifted")
    if "ITEMS_TEXT_SCOPE_CHECK_DIAGNOSTIC_ONLY" not in PHASE32_SEMANTIC_V2_SUPPORT_RULE:
        raise AssertionError("semantic V2 source-scope rule drifted")

    semantic = sources["packages/backtesting/phase32_semantic_feasibility_v2.py"]
    runner = sources["scripts/run_phase32_semantic_feasibility_v2.py"]

    for token in (
        '"target_outcome_rows_read": 0',
        '"protected_candidate_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"phase33_signal_to_trade_entry_satisfied": False',
        '"ticker_used_as_identity": False',
        '"exact_cik_identity"',
        '"exact_filing_date_identity"',
        '"supporting_text_nonblank"',
        '"items_text_scope_diagnostics"',
        '"is_acceptance_gate": False',
        '"all_disclosures_overlap_original_8k_index"',
    ):
        require(semantic, token, "semantic V2 source contract")

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
        forbid(semantic, bad, "outcome/trading or ticker-normalization authority")

    require(runner, "Stop here. Diagnose and repair", "root-cause-before-workaround rule")
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
        EXPECTED_CORE_V2,
        EXPECTED_REJECTED_V1,
        EXPECTED_SEMANTIC_V2,
        EXPECTED_RESEARCH_START,
        "scripts/run_phase32_semantic_feasibility_v2.py",
    ):
        require(docs, token, "synchronized Phase32 semantic V2 docs")
    require(docs.lower(), "root cause", "root-cause documentation")

    print("ATLAS Phase 32 semantic V2 source contracts: PASS")
    print(f"- accepted core V2 fingerprint pinned: {EXPECTED_CORE_V2}")
    print(f"- rejected semantic V1 fingerprint preserved: {EXPECTED_REJECTED_V1}")
    print(f"- corrected semantic V2 fingerprint pinned: {EXPECTED_SEMANTIC_V2}")
    print("- empirical semantic coverage is required at the 2021-08-16 Phase32 research boundary")
    print("- accession+CIK+SEC metadata define filing identity; ticker fields are mapping metadata only")
    print("- supporting_text remains mandatory; items_text lexical comparison is diagnostic because source scopes differ")
    print("- hypotheses and target/protected outcomes remain unopened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
