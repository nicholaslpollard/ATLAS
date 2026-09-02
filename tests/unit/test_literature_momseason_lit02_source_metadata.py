from __future__ import annotations

from datetime import date
from pathlib import PureWindowsPath

from packages.backtesting.literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
    LIT02_SOURCE_METADATA_INCOMPLETE,
    LIT02_SOURCE_METADATA_READY,
    build_source_coverage_report,
    classify_massive_ticker_events,
    parse_explicit_sec_ticker_change,
    parse_sec_terminal_transaction,
    select_identity_authorities,
)


def test_accepted_lit02_freeze_fingerprints_are_locked() -> None:
    assert (
        LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
        == "4768ac204a68bbc7d89fa64c96574934d1e4149169cd6c222ef16be5bc1367ae"
    )
    assert (
        LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
        == "c9200212a67171ee7c712a64224263241d622d2e8fe494ce0bc13843a8052880"
    )


def test_massive_composite_figi_ticker_event_resolves_stale_symbol() -> None:
    result = classify_massive_ticker_events(
        [
            {
                "type": "ticker_change",
                "date": "2021-09-20",
                "ticker_change": {"ticker": "VATE"},
            }
        ],
        endpoint_session=date(2021, 9, 30),
        historical_ticker="HCHC",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TICKER_CONTINUITY"
    assert result["new_ticker"] == "VATE"
    assert result["effective_date"] == "2021-09-20"


def test_massive_ticker_event_conflict_fails_closed() -> None:
    result = classify_massive_ticker_events(
        [
            {
                "type": "ticker_change",
                "date": "2022-01-03",
                "ticker_change": {"ticker": "AAA"},
            },
            {
                "type": "ticker_change",
                "date": "2022-01-03",
                "ticker_change": {"ticker": "BBB"},
            },
        ],
        endpoint_session=date(2022, 1, 31),
        historical_ticker="OLD",
    )
    assert result is not None
    assert result["status"] == "CONFLICT"
    assert result["reason"] == "MASSIVE_TICKER_EVENT_DATE_CONFLICT"


def test_sec_explicit_ticker_change_requires_effective_date_and_old_symbol_match() -> None:
    text = (
        "Effective September 20, 2021, the Company's trading symbol changed "
        'from "HCHC" to "VATE".'
    )
    result = parse_explicit_sec_ticker_change(
        text,
        endpoint_session=date(2021, 9, 30),
        historical_ticker="HCHC",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["new_ticker"] == "VATE"
    assert result["effective_date"] == "2021-09-20"

    assert (
        parse_explicit_sec_ticker_change(
            text,
            endpoint_session=date(2021, 9, 30),
            historical_ticker="OTHER",
        )
        is None
    )


def test_sec_terminal_cash_requires_closing_date_and_per_share_cash() -> None:
    text = (
        "On October 27, 2022, the parties completed the merger transaction. "
        "At the effective time, each outstanding share of common stock was "
        "converted into the right to receive $54.20 in cash per share."
    )
    result = parse_sec_terminal_transaction(
        text,
        endpoint_session=date(2022, 10, 31),
        historical_ticker="TWTR",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["effective_date"] == "2022-10-27"
    assert result["cash_per_share"] == 54.20


def test_sec_terminal_distribution_requires_explicit_per_share_value() -> None:
    text = (
        "On June 15, 2023, the company completed the liquidation transaction. "
        "The final liquidating distribution was $3.25 per share."
    )
    result = parse_sec_terminal_transaction(
        text,
        endpoint_session=date(2023, 6, 30),
        historical_ticker="OLD",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_DISTRIBUTION"
    assert result["distribution_per_share"] == 3.25


def test_stock_terminal_path_fails_closed_without_successor_ticker_identity() -> None:
    text = (
        "On March 10, 2024, the parties completed the merger transaction. "
        "Each share was converted into the right to receive 0.7500 shares of common stock."
    )
    result = parse_sec_terminal_transaction(
        text,
        endpoint_session=date(2024, 3, 28),
        historical_ticker="OLD",
    )
    assert result is not None
    assert result["path_id"] == "TERMINAL_STOCK"
    assert result["status"] == "INCOMPLETE"
    assert result["reason"] == "SUCCESSOR_TICKER_IDENTITY_REQUIRED"


def test_identity_authority_is_stable_and_conflicts_fail_closed() -> None:
    rows = [
        {
            "snapshot_date": "2022-09-30",
            "identity_quality": "strong",
            "ticker": "OLD",
            "composite_figi": "BBG000ABC123",
            "cik": "1234",
        },
        {
            "snapshot_date": "2022-10-31",
            "identity_quality": "strong",
            "ticker": "NEW",
            "composite_figi": "BBG000ABC123",
            "cik": "0000001234",
        },
    ]
    result = select_identity_authorities(
        rows,
        endpoint_session=date(2022, 10, 31),
        instrument_id="ins_test",
    )
    assert result["identity_status"] == "READY"
    assert result["composite_figi"] == "BBG000ABC123"
    assert result["cik"] == "0000001234"
    assert result["aliases"] == ["NEW", "OLD"]

    conflict_rows = [*rows, {**rows[-1], "composite_figi": "BBG999XYZ999"}]
    conflict = select_identity_authorities(
        conflict_rows,
        endpoint_session=date(2022, 10, 31),
        instrument_id="ins_test",
    )
    assert conflict["identity_status"] == "CONFLICT"
    assert "MULTIPLE_COMPOSITE_FIGIS" in conflict["identity_conflicts"]


def test_coverage_report_requires_100_percent_and_never_grants_phase33() -> None:
    ready_rows = [
        {
            "case_id": "a",
            "resolution_status": "RESOLVED",
            "path_id": "TERMINAL_CASH",
            "classification": {"path_id": "TERMINAL_CASH"},
            "unresolved_reasons": [],
        },
        {
            "case_id": "b",
            "resolution_status": "RESOLVED",
            "path_id": "TICKER_CONTINUITY",
            "classification": {"path_id": "TICKER_CONTINUITY"},
            "unresolved_reasons": [],
        },
    ]
    ready = build_source_coverage_report(
        case_results=ready_rows,
        provider_reads=3,
        massive_provider_reads=1,
        sec_provider_reads=2,
        cached_cases=0,
        identity_evidence_fingerprint="i" * 64,
    )
    assert ready["status"] == LIT02_SOURCE_METADATA_READY
    assert ready["source_coverage"] == 1.0
    assert ready["lit02_economic_design_unblocked"] is True
    assert ready["new_price_or_return_provider_reads"] == 0
    assert ready["protected_return_rows_read"] == 0
    assert ready["phase33_signal_to_trade_authority"] is False

    incomplete_rows = [
        ready_rows[0],
        {
            "case_id": "b",
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": ["NO_ADMISSIBLE_SEC_8K_EVIDENCE"],
        },
    ]
    incomplete = build_source_coverage_report(
        case_results=incomplete_rows,
        provider_reads=3,
        massive_provider_reads=1,
        sec_provider_reads=2,
        cached_cases=0,
        identity_evidence_fingerprint="i" * 64,
    )
    assert incomplete["status"] == LIT02_SOURCE_METADATA_INCOMPLETE
    assert incomplete["source_coverage"] == 0.5
    assert incomplete["lit02_economic_design_unblocked"] is False


def test_compact_metadata_storage_stays_below_legacy_windows_max_path() -> None:
    root = PureWindowsPath(
        r"C:\Users\cyberdyne\Desktop\ATLAS\data\derived\strategy_evaluation"
        r"\literature_anchored\momseason\v1\source\total_return_source"
        r"\native_population\research_freeze\development\l2\m"
    )
    final_path = root / "0123456789ab.json"
    temp_name = f"{final_path.name}.12345.{'f' * 32}.tmp"
    temp_path = final_path.with_name(temp_name)
    assert len(str(temp_path)) < 260
