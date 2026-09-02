from __future__ import annotations

from datetime import date

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2 import (
    LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
    _filtered_sec_rows_v2,
    _select_latest_ready,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
    parse_explicit_sec_ticker_change_v2_certified,
    parse_sec_terminal_transaction_v2_certified,
)


def test_twitter_style_date_before_merger_consummation_resolves_terminal_cash() -> None:
    text = """
    On October 27, 2022, pursuant to the terms of the Merger Agreement,
    Acquisition Sub merged with and into Twitter (the Merger), with Twitter
    surviving the Merger. Pursuant to the Merger Agreement, at the effective
    time of the Merger, each issued and outstanding share of Twitter common
    stock was canceled and converted into the right to receive $54.20 in cash,
    without interest. Item 2.01. On October 27, 2022, the Merger was consummated.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2022, 10, 31),
        historical_ticker="TWTR",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["effective_date"] == "2022-10-27"
    assert result["cash_per_share"] == 54.20
    assert result["parser_version"] == LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT
    assert (
        result["parser_certification"]
        == LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION
    )


def test_contextual_cash_prefers_executed_common_share_value_over_unrelated_values() -> None:
    text = """
    Earlier disclosures discussed an employee option with a per share exercise
    price of $12.00 and a financing reference price of $20.00 per share.
    On October 19, 2022, the merger was completed. At the Effective Time, each
    issued and outstanding share of common stock was automatically converted
    into the right to receive cash in an amount equal to $93.50, without interest,
    the Per Share Merger Consideration. An option paragraph later again refers
    to an exercise price of $12.00 per share.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2022, 10, 31),
        historical_ticker="AVLR",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["cash_per_share"] == 93.50


def test_scheduled_sec_ticker_change_can_be_verified_later_by_endpoint_identity() -> None:
    text = """
    The Company is expected to commence trading on the New York Stock Exchange
    under the trading symbol VATE at market open on September 20, 2021. Until
    that time, the Company will continue to trade on the New York Stock Exchange
    under its present symbol HCHC.
    """
    result = parse_explicit_sec_ticker_change_v2_certified(
        text,
        endpoint_session=date(2021, 9, 30),
        historical_ticker="HCHC",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TICKER_CONTINUITY"
    assert result["old_ticker"] == "HCHC"
    assert result["new_ticker"] == "VATE"
    assert result["effective_date"] == "2021-09-20"


def test_latest_effective_event_wins_over_earlier_valid_continuity_event() -> None:
    candidates = [
        {
            "status": "READY",
            "path_id": "TICKER_CONTINUITY",
            "old_ticker": "AAA",
            "new_ticker": "BBB",
            "effective_date": "2022-01-10",
        },
        {
            "status": "READY",
            "path_id": "TERMINAL_CASH",
            "cash_per_share": 25.0,
            "effective_date": "2022-03-15",
        },
    ]
    selected, conflict = _select_latest_ready(candidates)
    assert conflict is None
    assert selected is not None
    assert selected["path_id"] == "TERMINAL_CASH"
    assert selected["effective_date"] == "2022-03-15"


def test_same_day_incompatible_ready_candidates_fail_closed() -> None:
    candidates = [
        {
            "status": "READY",
            "path_id": "TERMINAL_CASH",
            "cash_per_share": 25.0,
            "effective_date": "2022-03-15",
        },
        {
            "status": "READY",
            "path_id": "TERMINAL_CASH",
            "cash_per_share": 26.0,
            "effective_date": "2022-03-15",
        },
    ]
    selected, conflict = _select_latest_ready(candidates)
    assert selected is None
    assert conflict == "MULTIPLE_SEC_READY_CLASSIFICATIONS_AT_LATEST_EFFECTIVE_DATE"


def test_6k_is_admissible_official_sec_metadata_but_irrelevant_8k_is_filtered() -> None:
    rows = [
        {
            "accessionNumber": "0000000001-22-000001",
            "filingDate": "2022-03-01",
            "form": "6-K",
            "items": "",
            "primaryDocument": "foreign.htm",
        },
        {
            "accessionNumber": "0000000001-22-000002",
            "filingDate": "2022-03-02",
            "form": "8-K",
            "items": "5.02",
            "primaryDocument": "officer.htm",
        },
        {
            "accessionNumber": "0000000001-22-000003",
            "filingDate": "2022-03-03",
            "form": "8-K",
            "items": "2.01",
            "primaryDocument": "merger.htm",
        },
    ]
    filtered = _filtered_sec_rows_v2(
        rows,
        start_date=date(2022, 1, 1),
        end_date=date(2022, 4, 1),
    )
    assert [item["form"] for item in filtered] == ["6-K", "8-K"]
    assert [item["accession_number"] for item in filtered] == [
        "0000000001-22-000001",
        "0000000001-22-000003",
    ]


def test_future_execution_date_is_not_admitted() -> None:
    text = """
    On November 15, 2022, the merger was consummated. Each issued and outstanding
    share was converted into the right to receive $10.00 in cash per share.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2022, 10, 31),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "INCOMPLETE"
    assert result["event_dates"] == []
