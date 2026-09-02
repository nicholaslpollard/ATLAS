from __future__ import annotations

from datetime import date

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION,
    parse_sec_final_transaction_amendment_v3_certified,
)


def test_defined_offer_price_links_to_executed_merger_without_backward_numeric_leakage() -> None:
    text = """
    The Offer Price is $27.00 per share. An employee option elsewhere has an
    exercise price of $4.00 per share.

    On June 16, 2026, following consummation of the Offer, Purchaser merged with
    and into the Company, with the Company surviving the Merger. At the Effective
    Time, each then-outstanding Share not purchased in the Offer was canceled and
    converted into the right to receive the Offer Price, without interest.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC TO-T/A",
        endpoint_session=date(2026, 6, 30),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["effective_date"] == "2026-06-16"
    assert result["cash_per_share"] == 27.0
    assert result["defined_term"] == "OFFER PRICE"
    assert (
        result["repair_v3_parser_certification"]
        == LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
    )


def test_value_before_defined_offer_price_is_supported_when_explicit_per_share_term() -> None:
    text = """
    Purchaser offered to acquire all Shares for $11.50 per share, the "Offer Price".
    On May 12, 2025, Parent completed the acquisition through the merger of
    Purchaser with and into the Company. Each outstanding Share not tendered in
    the Offer was canceled and converted into the right to receive the Offer Price.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC TO-T/A",
        endpoint_session=date(2025, 5, 30),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["cash_per_share"] == 11.5
    assert result["effective_date"] == "2025-05-12"


def test_final_13e3_defined_merger_consideration_is_supported() -> None:
    text = """
    The Merger Consideration means $35.00 per common share.
    This Final Amendment reports the results of the transaction.
    On July 1, 2021, the Company completed the merger of Merger Sub with and into
    the Company. At the Effective Time, each issued and outstanding common share
    was canceled and converted into the right to receive the Merger Consideration.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC 13E3/A",
        endpoint_session=date(2021, 7, 30),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["cash_per_share"] == 35.0
    assert result["defined_term"] == "MERGER CONSIDERATION"


def test_contingent_value_right_definition_fails_closed() -> None:
    text = """
    The Offer Price is $1.16 per share plus one contingent value right (CVR) per
    share that may produce additional cash payments.
    On January 26, 2024, Parent completed the acquisition through the merger of
    Merger Sub with and into the Company. At the Effective Time, each Share was
    canceled and converted into the right to receive the Offer Price.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC TO-T/A",
        endpoint_session=date(2024, 1, 31),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "INCOMPLETE"
    assert result["reason"] == "CONTINGENT_CONSIDERATION_NOT_SUPPORTED_V3"


def test_conflicting_defined_offer_prices_fail_closed() -> None:
    text = """
    The Offer Price is $10.00 per share. A later amendment states that the Offer
    Price is $11.00 per share.
    On March 15, 2024, Parent completed the acquisition through the merger of
    Merger Sub with and into the Company. Each Share was canceled and converted
    into the right to receive the Offer Price.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC TO-T/A",
        endpoint_session=date(2024, 3, 28),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "CONFLICT"
    assert result["reason"] == "MULTIPLE_DEFINED_TERMINAL_CASH_VALUES_V3"


def test_defined_term_linkage_is_not_enabled_for_excluded_forms() -> None:
    text = """
    The Offer Price is $20.00 per share.
    On April 2, 2024, Parent completed the acquisition through the merger of
    Merger Sub with and into the Company. Each Share was canceled and converted
    into the right to receive the Offer Price.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="DEFM14A",
        endpoint_session=date(2024, 4, 30),
        historical_ticker="AAA",
    )
    assert result is None or result.get("status") != "READY"


def test_future_execution_date_still_cannot_resolve_defined_term() -> None:
    text = """
    The Offer Price is $20.00 per share.
    On May 15, 2024, Parent completed the acquisition through the merger of
    Merger Sub with and into the Company. Each Share was canceled and converted
    into the right to receive the Offer Price.
    """
    result = parse_sec_final_transaction_amendment_v3_certified(
        text,
        form="SC TO-T/A",
        endpoint_session=date(2024, 4, 30),
        historical_ticker="AAA",
    )
    assert result is None or result.get("status") != "READY"
