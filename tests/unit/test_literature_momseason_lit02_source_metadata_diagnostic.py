from __future__ import annotations

import pytest

import packages.backtesting.literature_momseason_lit02_source_metadata_diagnostic as diagnostic
from packages.backtesting.literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
    LIT02_SOURCE_METADATA_CONTRACT,
    LIT02_SOURCE_METADATA_INCOMPLETE,
)


def _case_results() -> list[dict[str, object]]:
    return [
        {
            "case_id": "resolved",
            "endpoint_session": "2022-01-31",
            "historical_ticker": "AAA",
            "instrument_ids": ["ins_a"],
            "resolution_status": "RESOLVED",
            "path_id": "TERMINAL_CASH",
            "classification": {"path_id": "TERMINAL_CASH", "cash_per_share": 10.0},
            "unresolved_reasons": [],
            "instrument_results": [],
        },
        {
            "case_id": "date-gap",
            "endpoint_session": "2022-02-28",
            "historical_ticker": "BBB",
            "instrument_ids": ["ins_b"],
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": [
                "MASSIVE_TICKER_EVENTS_NOT_FOUND",
                "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
            ],
            "instrument_results": [
                {
                    "instrument_id": "ins_b",
                    "identity": {
                        "identity_status": "READY",
                        "composite_figi": "BBG000TEST01",
                        "cik": "0000000001",
                        "aliases": ["BBB"],
                        "safe_identity_rows": 2,
                        "nearby_identity_rows": 1,
                        "identity_conflicts": [],
                    },
                    "massive_evidence": {
                        "query_identifier": "BBG000TEST01",
                        "provider_status": "HTTP_404_NOT_FOUND",
                        "source_available": False,
                        "event_count": 0,
                        "candidate": None,
                    },
                    "sec_evidence": [
                        {
                            "accession_number": "0000000001-22-000001",
                            "filing_date": "2022-02-15",
                            "form": "8-K",
                            "items": ["2.01"],
                            "submission_source_sha256": "a" * 64,
                            "terminal_candidate": {
                                "status": "INCOMPLETE",
                                "reason": "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
                                "cash_values": [12.5],
                                "share_ratios": [],
                                "event_dates": [],
                            },
                            "ticker_change_candidate": None,
                        }
                    ],
                }
            ],
        },
        {
            "case_id": "cash-conflict",
            "endpoint_session": "2022-03-31",
            "historical_ticker": "CCC",
            "instrument_ids": ["ins_c"],
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": [
                "COMPOSITE_FIGI_UNAVAILABLE",
                "MULTIPLE_TERMINAL_CASH_VALUES",
            ],
            "instrument_results": [
                {
                    "instrument_id": "ins_c",
                    "identity": {
                        "identity_status": "READY",
                        "composite_figi": None,
                        "cik": "0000000002",
                        "aliases": ["CCC"],
                        "safe_identity_rows": 1,
                        "nearby_identity_rows": 1,
                        "identity_conflicts": [],
                    },
                    "massive_evidence": None,
                    "sec_evidence": [
                        {
                            "accession_number": "0000000002-22-000002",
                            "filing_date": "2022-03-10",
                            "form": "8-K",
                            "items": ["2.01"],
                            "submission_source_sha256": "b" * 64,
                            "terminal_candidate": {
                                "status": "CONFLICT",
                                "reason": "MULTIPLE_TERMINAL_CASH_VALUES",
                                "cash_values": [10.0, 20.0],
                            },
                            "ticker_change_candidate": None,
                        }
                    ],
                }
            ],
        },
    ]


def _source_report(case_results: list[dict[str, object]]) -> dict[str, object]:
    classification = diagnostic._classification_fingerprint(case_results)
    return {
        "status": LIT02_SOURCE_METADATA_INCOMPLETE,
        "contract_version": LIT02_SOURCE_METADATA_CONTRACT,
        "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "classification_fingerprint": classification,
        "report_fingerprint": "synthetic-report",
        "feasibility_cases": 3,
        "resolved_cases": 1,
        "unresolved_cases": 2,
        "economic_outcome_values_read": 0,
        "new_price_or_return_provider_reads": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "lit02_economic_design_unblocked": False,
    }


def _patch_acceptance(monkeypatch: pytest.MonkeyPatch, case_results: list[dict[str, object]]) -> None:
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_SOURCE_METADATA_CASES", 3)
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_SOURCE_METADATA_RESOLVED", 1)
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_SOURCE_METADATA_UNRESOLVED", 2)
    monkeypatch.setattr(
        diagnostic,
        "LIT02_ACCEPTED_SOURCE_METADATA_CLASSIFICATION_FINGERPRINT",
        diagnostic._classification_fingerprint(case_results),
    )
    monkeypatch.setattr(
        diagnostic,
        "LIT02_ACCEPTED_SOURCE_METADATA_REPORT_FINGERPRINT",
        "synthetic-report",
    )


def test_cached_diagnostic_separates_date_cash_identity_and_massive_mechanisms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _case_results()
    _patch_acceptance(monkeypatch, cases)
    report = diagnostic.build_source_metadata_diagnostic(
        source_report=_source_report(cases),
        case_results=cases,
    )

    assert report["status"] == diagnostic.LIT02_SOURCE_METADATA_DIAGNOSTIC_STATUS
    assert report["unresolved_cases"] == 2
    assert report["mechanism_counts"]["SEC_TERMINAL_DATE_ZERO_MATCHES"] == 1
    assert report["mechanism_counts"]["SEC_MULTIPLE_CASH_VALUES"] == 1
    assert report["mechanism_counts"]["MASSIVE_EVENT_SOURCE_NOT_FOUND"] == 1
    assert report["mechanism_counts"]["IDENTITY_NO_COMPOSITE_FIGI"] == 1
    assert report["terminal_effective_date_cases"]["zero_explicit_event_date_match"] == 1
    assert report["terminal_effective_date_cases"]["multiple_explicit_event_date_matches"] == 0
    assert report["multiple_cash_value_conflict_cases"] == 1
    assert report["identity_gap_cases"]["no_figi_but_cik_available"] == 1
    assert report["identity_gap_cases"]["massive_404_but_cik_available"] == 1
    assert report["provider_reads_performed"] == 0
    assert report["new_price_or_return_provider_reads"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["lit02_economic_design_unblocked"] is False


def test_reason_intersections_are_counted_without_forcing_exclusive_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _case_results()
    _patch_acceptance(monkeypatch, cases)
    report = diagnostic.build_source_metadata_diagnostic(
        source_report=_source_report(cases),
        case_results=cases,
    )
    combos = report["reason_combination_counts"]
    assert (
        combos[
            "MASSIVE_TICKER_EVENTS_NOT_FOUND + TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED"
        ]
        == 1
    )
    assert (
        report["reason_pair_counts"]
        ["COMPOSITE_FIGI_UNAVAILABLE + MULTIPLE_TERMINAL_CASH_VALUES"]
        == 1
    )


def test_diagnostic_refuses_protected_read(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = _case_results()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    source["protected_return_rows_read"] = 1
    with pytest.raises(RuntimeError, match="safety field is nonzero"):
        diagnostic.build_source_metadata_diagnostic(
            source_report=source,
            case_results=cases,
        )


def test_diagnostic_refuses_manifest_classification_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _case_results()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    changed = [dict(row) for row in cases]
    changed[1] = {**changed[1], "historical_ticker": "CHANGED"}
    with pytest.raises(RuntimeError, match="do not reproduce accepted classification"):
        diagnostic.build_source_metadata_diagnostic(
            source_report=source,
            case_results=changed,
        )
