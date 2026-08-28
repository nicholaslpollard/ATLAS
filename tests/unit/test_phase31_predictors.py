from __future__ import annotations

from datetime import date

from packages.backtesting.phase31_predictors import (
    PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS,
    PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS,
    IdentityInterval,
    classify_accession,
    resolve_identity_interval,
)


def _row(
    *,
    accession: str = "0000000001-25-000001",
    code: str = "P",
    ticker: str = "TEST",
) -> dict[str, object]:
    return {
        "accession_number": accession,
        "filing_date": "2025-01-10",
        "form_type": "4",
        "record_type": "transaction",
        "transaction_code": code,
        "security_type": "non-derivative",
        "transaction_acquired_disposed": "A" if code == "P" else "D",
        "transaction_shares": 100.0,
        "transaction_price_per_share": 10.0,
        "transaction_timeliness": "O",
        "aff_10b5_one": False,
        "equity_swap_involved": False,
        "not_subject_to_section_16": False,
        "is_officer": True,
        "is_director": False,
        "is_ten_percent_owner": False,
        "tickers": [ticker],
        "owner_cik": "0000000100",
        "issuer_cik": "0000000200",
    }


def test_valid_purchase_accession_is_classified_without_value_threshold() -> None:
    result, reason = classify_accession([_row()])
    assert reason is None
    assert result is not None
    assert result.direction == "PURCHASE"
    assert result.ticker == "TEST"
    assert result.transaction_shares_sum == 100.0
    assert result.transaction_gross_value_sum == 1000.0


def test_mixed_transaction_codes_fail_accession_purity() -> None:
    rows = [_row(code="P"), _row(code="S")]
    result, reason = classify_accession(rows)
    assert result is None
    assert reason == "TRANSACTION_CODE_NOT_PURE_P_OR_S"


def test_missing_or_multiticker_linkage_is_fail_closed() -> None:
    row = _row()
    row["tickers"] = ["TEST", "TEST.B"]
    result, reason = classify_accession([row])
    assert result is None
    assert reason == "TICKER_ASSOCIATION_NOT_EXACTLY_ONE"


def test_10b5_one_true_is_excluded_but_null_is_not_affirmative() -> None:
    flagged = _row()
    flagged["aff_10b5_one"] = True
    result, reason = classify_accession([flagged])
    assert result is None
    assert reason == "AFF_10B5_ONE_TRUE"

    unknown = _row()
    unknown["aff_10b5_one"] = None
    result, reason = classify_accession([unknown])
    assert reason is None
    assert result is not None


def test_identity_resolution_requires_one_composite_figi_interval_covering_exit() -> None:
    interval = IdentityInterval(
        instrument_id="inst_test",
        ticker="TEST",
        valid_from_date=date(2020, 1, 1),
        valid_to_date_exclusive=date(2025, 2, 1),
        composite_figi="BBG000TEST",
    )
    resolved, reason = resolve_identity_interval(
        ticker="TEST",
        decision_session=date(2025, 1, 13),
        exit_session=date(2025, 1, 31),
        intervals={"TEST": (interval,)},
    )
    assert reason is None
    assert resolved == interval

    resolved, reason = resolve_identity_interval(
        ticker="TEST",
        decision_session=date(2025, 1, 13),
        exit_session=date(2025, 2, 3),
        intervals={"TEST": (interval,)},
    )
    assert resolved is None
    assert reason == "PIT_IDENTITY_INTERVAL_DOES_NOT_COVER_EXIT"


def test_accepted_full_history_counts_are_frozen_before_performance() -> None:
    assert PHASE31_ACCEPTED_FULL_HISTORY_RAW_ROWS == 2_993_648
    assert PHASE31_ACCEPTED_FULL_HISTORY_AUTHORITATIVE_ROWS == 2_992_608
