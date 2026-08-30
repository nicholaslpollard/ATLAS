from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY = "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67"
EXPECTED_PREDICTOR_CONTRACT = (
    "phase31-predictor-report-v1-form4-pure-open-market-pit-identity-no-market-outcomes"
)
EXPECTED_COUNTS = (2_993_648, 2_992_608, 1_040, 187, 233, 15, 62)
EXPECTED_CANDIDATES = (
    "open_market_purchase_long",
    "clustered_open_market_purchase_long",
    "open_market_sale_short",
    "clustered_open_market_sale_short",
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
    predictor = read("packages/backtesting/phase31_predictors.py")
    runner = read("scripts/run_phase31_form4_predictors.py")
    acquisition_doc = read("docs/phase31_full_historical_acquisition.md")
    scientific = read("docs/phase31_scientific_contract.md")
    flow = read("docs/phase_flow.md")
    for path, text in (
        ("packages/backtesting/phase31_predictors.py", predictor),
        ("scripts/run_phase31_form4_predictors.py", runner),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.phase31_policy import phase31_policy_fingerprint
    from packages.backtesting.phase31_predictors import (
        PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
        PHASE31_ACCEPTED_FULL_HISTORY_CHRONOLOGY_SEEDS,
        PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS,
        PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS,
        PHASE31_ACCEPTED_FULL_HISTORY_MONTH_SHARDS,
        PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS,
        PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
        PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION,
    )

    if phase31_policy_fingerprint() != EXPECTED_POLICY:
        raise AssertionError("Phase31 policy fingerprint drifted")
    if PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION != EXPECTED_PREDICTOR_CONTRACT:
        raise AssertionError("Phase31 predictor contract drifted")
    actual_counts = (
        PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
        PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
        PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS,
        PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS,
        PHASE31_ACCEPTED_FULL_HISTORY_CHRONOLOGY_SEEDS,
        PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS,
        PHASE31_ACCEPTED_FULL_HISTORY_MONTH_SHARDS,
    )
    if actual_counts != EXPECTED_COUNTS:
        raise AssertionError(f"accepted Phase31 acquisition evidence drifted: {actual_counts}")

    for candidate in EXPECTED_CANDIDATES:
        require(predictor, candidate, "frozen candidate membership")
    for required in (
        "classify_accession",
        "transaction_acquired_disposed",
        "TRANSACTION_CODE_NOT_PURE_P_OR_S",
        "AFF_10B5_ONE_TRUE",
        "TICKER_ASSOCIATION_NOT_EXACTLY_ONE",
        "CONTRADICTORY_PURCHASE_SALE_TICKER_SESSION",
        "PHASE31_CLUSTER_LOOKBACK_SESSIONS",
        "PHASE31_CLUSTER_MIN_DISTINCT_OWNERS",
        "PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS",
        "authoritative_ticker_intervals_file",
        "query_identifier_type = 'composite_figi'",
        "PIT_IDENTITY_INTERVAL_DOES_NOT_COVER_EXIT",
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
    ):
        require(predictor, required, "predictor contract")

    for forbidden in (
        "canonical_file(",
        "feature_file(",
        "derived_file(",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
        "forward_return =",
        "directional_return =",
        "future_close =",
        "stock_return =",
        "spy_return =",
    ):
        forbid(predictor, forbidden, "outcome/trading dependency")

    require(runner, "Market prices/outcomes/protected returns: FORBIDDEN / UNREAD", "runner blindness")
    require(runner, "Provider/broker/order/PAPER/LIVE/automation: DISABLED", "runner authority")
    require(acquisition_doc, "2,993,648", "accepted raw rows")
    require(acquisition_doc, "2,992,608", "accepted authoritative rows")
    require(acquisition_doc, "1,040", "accepted quarantine rows")
    require(scientific, "split/corporate-action crossings", "remaining path-admissibility requirement")

    # phase_flow.md is a living continuation document. Phase31 predictor invariants are
    # frozen above; the living handoff may advance beyond Phase32 as long as it preserves
    # the historical disposition and the current no-support/no-protected-read authority.
    require(flow, "Accepted project foundation: **through Phase32**", "accepted foundation boundary")
    require(flow, "Phases26–32 are `ACCEPTED_NEGATIVE`", "retained modern alpha dispositions")
    require(flow, "SEC XBRL fundamental-quality/accrual research program has now also closed **`ACCEPTED_NEGATIVE`**", "current XBRL disposition")
    require(flow, "XBRL protected return rows read = **0**; protected holdout consumed = **false**", "current protected blindness boundary")
    require(flow, "Master protected window `2026-05-12..2026-08-11` remains unconsumed", "master holdout continuity")
    require(flow, "Phase33 Signal-to-Trade Construction remains blocked", "current downstream authority boundary")

    print("ATLAS Phase 31 predictor-only Form-4 contracts: PASS")
    print("- accepted 62-shard acquisition evidence is frozen before performance")
    print("- exact P/S eligibility, contradiction, cluster and Composite-FIGI PIT identity rules are bound")
    print("- predictor construction has no market-price/return or trading authority")
    print("- historical Phase31 predictor invariants remain frozen while living phase_flow advances through the completed XBRL closeout")
    print("- master protected evidence remains unread/unconsumed and Phase33 remains blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
