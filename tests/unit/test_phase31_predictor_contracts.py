from __future__ import annotations

import ast
from pathlib import Path

from packages.backtesting.phase31_predictors import (
    PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
    PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS,
    PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS,
    PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS,
    PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
    PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION,
)


ROOT = Path(__file__).resolve().parents[2]


def test_predictor_contract_binds_accepted_acquisition_evidence() -> None:
    assert PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION == (
        "phase31-predictor-report-v1-form4-pure-open-market-pit-identity-no-market-outcomes"
    )
    assert PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS == 2_993_648
    assert PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS == 2_992_608
    assert PHASE31_ACCEPTED_FULL_HISTORY_QUARANTINED_ROWS == 1_040
    assert PHASE31_ACCEPTED_FULL_HISTORY_CONTAMINATED_ACCESSIONS == 187
    assert PHASE31_ACCEPTED_FULL_HISTORY_MISSING_CODE_SEEDS == 15


def test_predictor_runtime_has_no_market_or_trading_dependency() -> None:
    path = ROOT / "packages" / "backtesting" / "phase31_predictors.py"
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    for forbidden in (
        "canonical_file(",
        "feature_file(",
        "derived_file(",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
        "stock_return =",
        "spy_return =",
    ):
        assert forbidden not in text
    assert "authoritative_ticker_intervals_file" in text
    assert "query_identifier_type = 'composite_figi'" in text
    assert '"target_outcome_rows_read": 0' in text
    assert '"protected_return_rows_read": 0' in text


def test_predictor_runner_keeps_return_and_trade_authority_closed() -> None:
    text = (ROOT / "scripts" / "run_phase31_form4_predictors.py").read_text(encoding="utf-8")
    ast.parse(text)
    assert "Market prices/outcomes/protected returns: FORBIDDEN / UNREAD" in text
    assert "Provider/broker/order/PAPER/LIVE/automation: DISABLED" in text
