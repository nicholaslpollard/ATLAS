from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_V2 = "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
EXPECTED_SEMANTIC_V1 = "ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82"
EXPECTED_V1_CONTRACT = (
    "phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes"
)


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
        "scripts/diagnose_phase32_semantic_failure.py",
        "tests/unit/test_phase32_semantic_feasibility.py",
    )
    sources = {path: read(path) for path in paths}
    for path, source in sources.items():
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_semantic_feasibility import (
        PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT,
        PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN,
        PHASE32_SEMANTIC_CONTRACT_VERSION,
        PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED,
        PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED,
        phase32_semantic_feasibility_fingerprint,
    )
    from packages.providers.massive.phase32_semantic import (
        PHASE32_DISCLOSURES_ENDPOINT,
        PHASE32_TEXT_ENDPOINT,
        PHASE32_TAXONOMY_ENDPOINT,
    )

    if PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT != EXPECTED_V2:
        raise AssertionError("accepted Phase32 V2 fingerprint drifted")
    if PHASE32_SEMANTIC_CONTRACT_VERSION != EXPECTED_V1_CONTRACT:
        raise AssertionError("retained semantic V1 contract drifted")
    if phase32_semantic_feasibility_fingerprint() != EXPECTED_SEMANTIC_V1:
        raise AssertionError("retained semantic V1 fingerprint drifted")
    if PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("Phase32 hypotheses froze during semantic source diagnosis")
    if PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED or PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED:
        raise AssertionError("Phase32 semantic source work may not read market outcomes")

    if PHASE32_DISCLOSURES_ENDPOINT != "/stocks/filings/8-K/vX/disclosures":
        raise AssertionError("Phase32 disclosures endpoint drifted")
    if PHASE32_TEXT_ENDPOINT != "/stocks/filings/8-K/vX/text":
        raise AssertionError("Phase32 8-K text endpoint drifted")
    if PHASE32_TAXONOMY_ENDPOINT != "/stocks/taxonomies/vX/disclosures":
        raise AssertionError("Phase32 taxonomy endpoint drifted")

    semantic = sources["packages/backtesting/phase32_semantic_feasibility.py"]
    adapter = sources["packages/providers/massive/phase32_semantic.py"]
    runner = sources["scripts/run_phase32_semantic_feasibility.py"]
    diagnostic = sources["scripts/diagnose_phase32_semantic_failure.py"]

    for token in (
        '"target_outcome_rows_read": 0',
        '"protected_candidate_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"phase33_signal_to_trade_entry_satisfied": False',
        "supporting_text_grounded_in_items_text",
        "ticker_aligned",
    ):
        require(semantic, token, "retained semantic V1 source contract")

    for bad in (
        "packages.execution",
        "packages.brokers",
        ".submit_order(",
        ".place_order(",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
    ):
        forbid(semantic + "\n" + adapter + "\n" + diagnostic, bad, "outcome/trading authority")

    require(runner, "Stop here. Diagnose and repair", "V1 failure-stop rule")
    require(diagnostic, "Market outcomes read: 0", "diagnostic zero-outcome declaration")
    require(diagnostic, "disclosure_tickers", "ticker mismatch diagnostic")
    require(diagnostic, "support_token_coverage_in_items", "text-grounding diagnostic")

    docs = "\n".join(
        read(path)
        for path in (
            "README.md",
            "docs/current_status.md",
            "docs/phase32_sec_8k_material_event_alpha.md",
            "docs/phase32_semantic_source_qualification.md",
        )
    )
    for token in (
        EXPECTED_V2,
        EXPECTED_SEMANTIC_V1,
        "NOT ACCEPTED",
        "all_sampled_tickers_align",
        "all_sampled_supporting_text_is_grounded",
        "scripts/diagnose_phase32_semantic_failure.py",
        "Plan History is **not applicable**",
    ):
        require(docs, token, "synchronized Phase32 semantic failure docs")
    require(docs.lower(), "root cause", "root-cause-before-workaround documentation")
    require(docs.lower(), "january-2022", "rejected unsupported history-boundary documentation")

    print("ATLAS Phase 32 semantic source diagnostic state: PASS")
    print(f"- accepted core V2 fingerprint pinned: {EXPECTED_V2}")
    print(f"- rejected semantic V1 fingerprint retained: {EXPECTED_SEMANTIC_V1}")
    print("- V1 ticker and supporting-text failures are preserved, not weakened")
    print("- unsupported January-2022 history assumption is explicitly rejected")
    print("- local diagnostic reads source evidence only; hypotheses and outcomes remain unopened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
