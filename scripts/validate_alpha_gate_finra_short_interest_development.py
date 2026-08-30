from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_SCIENTIFIC = "0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f"
EXPECTED_IMPLEMENTATION = "f5b99a52bf0e9d101b53493e0012a7a60d24b301f904d4b9958dc03638432a5f"
EXPECTED_PREDICTOR = "alpha-gate-finra-short-interest-predictor-v1-source-only-change-crowding-ranked"
EXPECTED_DEVELOPMENT = "alpha-gate-finra-short-interest-development-v1-63-session-spy-relative-protected-blind"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    predictor_path = "packages/backtesting/alpha_gate_finra_short_interest_predictor.py"
    development_path = "packages/backtesting/alpha_gate_finra_short_interest_development.py"
    runner_path = "scripts/run_alpha_gate_finra_short_interest_development.py"
    predictor = read(predictor_path)
    development = read(development_path)
    runner = read(runner_path)
    workflow = read(".github/workflows/finra-short-interest-alpha-gate-tests.yml")
    for path, text in (
        (predictor_path, predictor),
        (development_path, development),
        (runner_path, runner),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_finra_short_interest_development import (
        FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT,
        FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        FINRA_SHORT_INTEREST_FINALIST_CONTRACT,
        FINRA_SHORT_INTEREST_OUTCOME_CONTRACT,
        development_implementation_fingerprint,
    )
    from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
        FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
        frozen_settlement_dates,
    )
    from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
        FINRA_SHORT_INTEREST_HYPOTHESES,
        FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    )

    if FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT != EXPECTED_SCIENTIFIC:
        raise AssertionError("scientific fingerprint drifted")
    if FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT != EXPECTED_IMPLEMENTATION:
        raise AssertionError("development implementation fingerprint drifted")
    if development_implementation_fingerprint() != EXPECTED_IMPLEMENTATION:
        raise AssertionError("computed development implementation fingerprint drifted")
    if FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT != EXPECTED_PREDICTOR:
        raise AssertionError("predictor contract drifted")
    if FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT != EXPECTED_DEVELOPMENT:
        raise AssertionError("development contract drifted")
    if FINRA_SHORT_INTEREST_OUTCOME_CONTRACT != "alpha-gate-finra-short-interest-outcome-v1-exact-open-t63-close-spy-relative-split-censored":
        raise AssertionError("outcome contract drifted")
    if FINRA_SHORT_INTEREST_FINALIST_CONTRACT != "alpha-gate-finra-short-interest-finalists-v1-selection-internal-protected-source-precheck-returns-unread":
        raise AssertionError("finalist contract drifted")
    if [spec.candidate_id for spec in FINRA_SHORT_INTEREST_HYPOTHESES] != [
        "rapid_short_build_crowded_short",
        "rapid_short_build_non_crowded_short",
        "rapid_short_cover_crowded_long",
        "rapid_short_cover_non_crowded_long",
    ]:
        raise AssertionError("finite candidate family drifted")

    schedule = frozen_settlement_dates()
    if not schedule or schedule[0].isoformat() != "2021-06-30" or schedule[-1].isoformat() != "2026-04-15":
        raise AssertionError("frozen FINRA settlement schedule boundary drifted")
    if len(schedule) != 116 or len(set(schedule)) != 116:
        raise AssertionError("frozen FINRA settlement schedule cardinality drifted")

    for required in (
        "SOURCE_ONLY_PREDICTOR_PASS",
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        "FINRA_SHORT_INTEREST_MAX_ROWS_PER_CANDIDATE_PER_SETTLEMENT",
        "_average_tie_percentiles",
        "_candidate",
    ):
        require(predictor, required, "source-only predictor boundary")
    for forbidden in (
        "read_parquet(",
        "connect_utc(",
        "MarketDataPaths",
        "stock_return",
        "spy_return",
        "future_close",
        "packages.execution",
        "packages.brokers",
        "submit_order(",
        "place_order(",
    ):
        forbid(predictor, forbidden, "outcome/trading dependency in predictor")

    for required in (
        'report.get("status") != "SOURCE_ONLY_PREDICTOR_PASS"',
        "read_parquet(",
        "HOLM_BONFERRONI_GLOBAL_4",
        "selection_passers",
        "internal_finalists",
        "protected_source_prechecks",
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"phase33_signal_to_trade_authority": False',
    ):
        require(development, required, "development governance boundary")
    for forbidden in (
        "packages.execution",
        "packages.brokers",
        "submit_order(",
        "place_order(",
        "paper_submit(",
    ):
        forbid(development, forbidden, "trading dependency in development")

    require(runner, "Stage 1: reconstruct complete source-only predictor population", "two-stage runner")
    require(runner, "if predictor.get(\"pass\") is not True", "source gate before outcomes")
    require(runner, "Protected returns: SEALED / UNREAD", "protected blindness")
    forbid(runner, "argparse", "operator policy override")
    require(workflow, "validate_alpha_gate_finra_short_interest_development.py", "focused implementation validator")
    require(workflow, "test_alpha_gate_finra_short_interest_predictor.py", "predictor tests")
    require(workflow, "test_alpha_gate_finra_short_interest_development.py", "development tests")

    print("ATLAS FINRA short-interest predictor/development implementation: PASS")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC}")
    print(f"- development implementation fingerprint: {EXPECTED_IMPLEMENTATION}")
    print("- 116 frozen twice-monthly settlement dates are reconstructed source-only")
    print("- development outcomes cannot open unless complete source-only predictor gate passes")
    print("- protected returns and trading/Phase33 authority remain sealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
