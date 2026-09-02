from __future__ import annotations

import pytest

from packages.backtesting.literature_momseason_native_population import (
    MOMSEASON_NATIVE_FORMATION_EXCHANGES,
    MOMSEASON_NATIVE_HISTORY_EXCHANGES,
    MOMSEASON_NATIVE_SECURITY_TYPE,
    _formation_row_status,
    _formula_defined,
    _historical_row_status,
    _supplemental_rows,
)


def _formation_row(
    *,
    exchange: str = "XNYS",
    security_type: str = "CS",
    quality: str = "strong",
    ticker: str = "AAA",
) -> dict[str, object]:
    return {
        "instrument_id": "i1",
        "identity_quality": quality,
        "ticker": ticker,
        "market": "stocks",
        "locale": "us",
        "primary_exchange": exchange,
        "security_type": security_type,
        "active": True,
        "delisted_utc": None,
    }


def _history_row(
    *,
    exchange: str = "XNYS",
    security_type: str = "CS",
    quality: str = "strong",
    ticker: str = "AAA",
) -> dict[str, object]:
    return {
        "instrument_id": "i1",
        "identity_quality": quality,
        "ticker": ticker,
        "primary_exchange": exchange,
        "security_type": security_type,
        "active": True,
    }


def test_native_formation_rule_is_nyse_amex_common_stock_only() -> None:
    assert MOMSEASON_NATIVE_FORMATION_EXCHANGES == {"XNYS", "XASE"}
    assert MOMSEASON_NATIVE_SECURITY_TYPE == "CS"

    row, status = _formation_row_status([_formation_row(exchange="XNYS")])
    assert status == "OK"
    assert row is not None

    row, status = _formation_row_status([_formation_row(exchange="XASE")])
    assert status == "OK"
    assert row is not None

    row, status = _formation_row_status([_formation_row(exchange="XNAS")])
    assert row is None
    assert status == "NOT_NATIVE_FORMATION_STOCK"

    row, status = _formation_row_status([_formation_row(security_type="ETF")])
    assert row is None
    assert status == "NOT_NATIVE_FORMATION_STOCK"


def test_formation_identity_ambiguity_and_fallback_are_not_silently_used() -> None:
    row, status = _formation_row_status(
        [_formation_row(ticker="AAA"), _formation_row(ticker="AAA.B")]
    )
    assert row is None
    assert status == "FORMATION_AMBIGUOUS_ACTIVE_LISTING"

    row, status = _formation_row_status([_formation_row(quality="fallback")])
    assert row is not None
    assert status == "FORMATION_IDENTITY_UNSAFE"


def test_historical_signal_month_matches_open_source_ap_major_common_stock_scope() -> None:
    assert MOMSEASON_NATIVE_HISTORY_EXCHANGES == {"XNYS", "XASE", "XNAS"}

    for exchange in ("XNYS", "XASE", "XNAS"):
        row, status = _historical_row_status(
            [_history_row(exchange=exchange)],
            require_signal_master_membership=True,
        )
        assert row is not None
        assert status == "OK"

    row, status = _historical_row_status(
        [_history_row(exchange="ARCX")],
        require_signal_master_membership=True,
    )
    assert row is None
    assert status == "HISTORICAL_NOT_COMMON_MAJOR_EXCHANGE"

    row, status = _historical_row_status(
        [_history_row(security_type="ADRC")],
        require_signal_master_membership=True,
    )
    assert row is None
    assert status == "HISTORICAL_NOT_COMMON_MAJOR_EXCHANGE"


def test_prior_price_anchor_does_not_apply_a_second_portfolio_membership_filter() -> None:
    row, status = _historical_row_status(
        [_history_row(exchange="ARCX")],
        require_signal_master_membership=False,
    )
    assert row is not None
    assert status == "OK"


def test_available_history_rule_requires_one_valid_lag_not_all_four() -> None:
    assert _formula_defined("momseason_short_year1", 0) is False
    assert _formula_defined("momseason_short_year1", 1) is True
    assert _formula_defined("momseason_years2_5", 0) is False
    assert _formula_defined("momseason_years2_5", 1) is True
    assert _formula_defined("momseason_years2_5", 4) is True


def test_supplemental_plan_reuses_existing_endpoint_keys() -> None:
    native = [
        {
            "endpoint_session": "2020-01-31",
            "instrument_id": "i1",
            "historical_ticker": "AAA",
        },
        {
            "endpoint_session": "2020-02-28",
            "instrument_id": "i1",
            "historical_ticker": "AAA",
        },
    ]
    prior = {
        ("2020-01-31", "i1"): {
            "historical_ticker": "AAA",
            "availability_status": "AVAILABLE",
        }
    }
    missing, reused = _supplemental_rows(native, prior)
    assert reused == 1
    assert missing == [native[1]]


def test_supplemental_plan_refuses_historical_ticker_conflict() -> None:
    native = [
        {
            "endpoint_session": "2020-01-31",
            "instrument_id": "i1",
            "historical_ticker": "AAA",
        }
    ]
    prior = {
        ("2020-01-31", "i1"): {
            "historical_ticker": "BBB",
            "availability_status": "AVAILABLE",
        }
    }
    with pytest.raises(RuntimeError, match="historical ticker"):
        _supplemental_rows(native, prior)
