from __future__ import annotations

import pytest

import packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2_diagnostic as diagnostic
from packages.backtesting.literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2 import (
    LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
    LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE,
)


def _cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "resolved",
            "endpoint_session": "2024-01-31",
            "historical_ticker": "AAA",
            "instrument_ids": ["ins_a"],
            "resolution_status": "RESOLVED",
            "path_id": "TERMINAL_CASH",
            "classification": {"path_id": "TERMINAL_CASH", "cash_per_share": 20.0},
            "unresolved_reasons": [],
            "instrument_results": [],
        },
        {
            "case_id": "date-gap",
            "endpoint_session": "2024-02-29",
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
                    },
                    "massive_evidence": {
                        "query_identifier": "BBG000TEST01",
                        "provider_status": "HTTP_404_NOT_FOUND",
                        "source_available": False,
                        "event_count": 0,
                    },
                    "sec_evidence": [
                        {
                            "accession_number": "0000000001-24-000001",
                            "filing_date": "2024-02-10",
                            "form": "8-K",
                            "submission_source_sha256": "a" * 64,
                            "ticker_change_candidate": None,
                            "terminal_candidate": {
                                "status": "INCOMPLETE",
                                "reason": "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
                                "cash_values": [12.5],
                                "share_ratios": [],
                                "distribution_values": [],
                                "event_dates": [],
                            },
                        }
                    ],
                }
            ],
        },
        {
            "case_id": "context-gap",
            "endpoint_session": "2024-03-28",
            "historical_ticker": "CCC",
            "instrument_ids": ["ins_c"],
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": ["TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED"],
            "instrument_results": [
                {
                    "instrument_id": "ins_c",
                    "identity": {
                        "identity_status": "READY",
                        "composite_figi": "BBG000TEST02",
                        "cik": "0000000002",
                        "aliases": ["CCC"],
                    },
                    "massive_evidence": None,
                    "sec_evidence": [
                        {
                            "accession_number": "0000000002-24-000002",
                            "filing_date": "2024-03-20",
                            "form": "6-K",
                            "submission_source_sha256": "b" * 64,
                            "ticker_change_candidate": None,
                            "terminal_candidate": {
                                "status": "INCOMPLETE",
                                "reason": "TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED",
                                "cash_values": [7.0],
                                "share_ratios": [0.5],
                                "distribution_values": [],
                                "event_dates": ["2024-03-15"],
                            },
                        }
                    ],
                }
            ],
        },
        {
            "case_id": "cash-conflict",
            "endpoint_session": "2024-04-30",
            "historical_ticker": "DDD",
            "instrument_ids": ["ins_d"],
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": [
                "COMPOSITE_FIGI_UNAVAILABLE",
                "MULTIPLE_TERMINAL_CASH_VALUES",
            ],
            "instrument_results": [
                {
                    "instrument_id": "ins_d",
                    "identity": {
                        "identity_status": "READY",
                        "composite_figi": None,
                        "cik": "0000000003",
                        "aliases": ["DDD"],
                    },
                    "massive_evidence": None,
                    "sec_evidence": [
                        {
                            "accession_number": "0000000003-24-000003",
                            "filing_date": "2024-04-12",
                            "form": "8-K/A",
                            "submission_source_sha256": "c" * 64,
                            "ticker_change_candidate": None,
                            "terminal_candidate": {
                                "status": "CONFLICT",
                                "reason": "MULTIPLE_TERMINAL_CASH_VALUES",
                                "cash_values": [10.0, 11.0],
                                "effective_date": "2024-04-10",
                                "all_event_dates": ["2024-04-10"],
                            },
                        }
                    ],
                }
            ],
        },
        {
            "case_id": "bound",
            "endpoint_session": "2024-05-31",
            "historical_ticker": "EEE",
            "instrument_ids": ["ins_e"],
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": [
                "LIT-02 repair-v2 SEC source lookup exceeded bounded candidate filing count: 146 > 128"
            ],
            "instrument_results": [
                {
                    "instrument_id": "ins_e",
                    "identity": {
                        "identity_status": "READY",
                        "composite_figi": "BBG000TEST03",
                        "cik": "0000000004",
                        "aliases": ["EEE"],
                    },
                    "massive_evidence": None,
                    "sec_evidence": [],
                }
            ],
        },
    ]


def _source_report(cases: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE,
        "contract_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
        "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "classification_fingerprint": diagnostic._classification_fingerprint(cases),
        "report_fingerprint": "synthetic-report-v2",
        "feasibility_cases": 5,
        "resolved_cases": 1,
        "unresolved_cases": 4,
        "newly_resolved_cases": 1,
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
        "phase33_signal_to_trade_authority": False,
    }


def _patch_acceptance(monkeypatch: pytest.MonkeyPatch, cases: list[dict[str, object]]) -> None:
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_REPAIR_V2_CASES", 5)
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_REPAIR_V2_RESOLVED", 1)
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED", 4)
    monkeypatch.setattr(diagnostic, "LIT02_ACCEPTED_REPAIR_V2_NEWLY_RESOLVED", 1)
    monkeypatch.setattr(
        diagnostic,
        "LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT",
        diagnostic._classification_fingerprint(cases),
    )
    monkeypatch.setattr(
        diagnostic,
        "LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT",
        "synthetic-report-v2",
    )


def test_residual_diagnostic_separates_v2_source_mechanisms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    report = diagnostic.build_repair_v2_residual_diagnostic(
        source_report=_source_report(cases),
        case_results=cases,
    )

    assert report["status"] == diagnostic.LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_STATUS
    assert report["unresolved_cases"] == 4
    assert report["mechanism_counts"]["SEC_TERMINAL_EFFECTIVE_DATE_UNRESOLVED"] == 1
    assert report["mechanism_counts"]["SEC_TERMINAL_CONTEXT_UNRESOLVED"] == 1
    assert report["mechanism_counts"]["SEC_MULTIPLE_TERMINAL_CASH_VALUES"] == 1
    assert report["mechanism_counts"]["SEC_CANDIDATE_FILING_BOUND_EXCEEDED"] == 1
    assert report["mechanism_counts"]["MASSIVE_EVENT_SOURCE_NOT_FOUND"] == 1
    assert report["mechanism_counts"]["IDENTITY_NO_COMPOSITE_FIGI"] == 1
    assert report["date_unresolved_value_profiles"] == {"CASH": 1}
    assert report["context_unresolved_value_profiles"] == {"CASH+SHARES": 1}
    assert report["multiple_cash_value_conflict_cases"] == 1
    assert report["sec_residual_case_modes"]["candidate_filing_bound_exceeded"] == 1
    assert report["provider_reads_performed"] == 0
    assert report["economic_outcome_values_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["lit02_economic_design_unblocked"] is False


def test_residual_diagnostic_counts_forms_and_reason_intersections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    report = diagnostic.build_repair_v2_residual_diagnostic(
        source_report=_source_report(cases),
        case_results=cases,
    )
    assert report["sec_form_counts"] == {"6-K": 1, "8-K": 1, "8-K/A": 1}
    assert (
        report["reason_pair_counts"][
            "MASSIVE_TICKER_EVENTS_NOT_FOUND + TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED"
        ]
        == 1
    )
    assert (
        report["reason_pair_counts"][
            "COMPOSITE_FIGI_UNAVAILABLE + MULTIPLE_TERMINAL_CASH_VALUES"
        ]
        == 1
    )


def test_residual_diagnostic_refuses_protected_read(monkeypatch: pytest.MonkeyPatch) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    source["protected_return_rows_read"] = 1
    with pytest.raises(RuntimeError, match="safety field is nonzero"):
        diagnostic.build_repair_v2_residual_diagnostic(
            source_report=source,
            case_results=cases,
        )


def test_residual_diagnostic_refuses_unblocked_economic_design(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    source["lit02_economic_design_unblocked"] = True
    with pytest.raises(RuntimeError, match="refuses unblocked economic design"):
        diagnostic.build_repair_v2_residual_diagnostic(
            source_report=source,
            case_results=cases,
        )


def test_residual_diagnostic_refuses_phase33_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    source["phase33_signal_to_trade_authority"] = True
    with pytest.raises(RuntimeError, match="refuses Phase33 authority"):
        diagnostic.build_repair_v2_residual_diagnostic(
            source_report=source,
            case_results=cases,
        )


def test_residual_diagnostic_refuses_manifest_classification_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    changed = [dict(row) for row in cases]
    changed[1] = {**changed[1], "unresolved_reasons": ["NO_ADMISSIBLE_OFFICIAL_SEC_EVIDENCE_V2"]}
    with pytest.raises(RuntimeError, match="do not reproduce accepted classification"):
        diagnostic.build_repair_v2_residual_diagnostic(
            source_report=_source_report(cases),
            case_results=changed,
        )


def test_residual_diagnostic_refuses_report_fingerprint_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _cases()
    _patch_acceptance(monkeypatch, cases)
    source = _source_report(cases)
    source["report_fingerprint"] = "wrong"
    with pytest.raises(RuntimeError, match="report fingerprint mismatch"):
        diagnostic.build_repair_v2_residual_diagnostic(
            source_report=source,
            case_results=cases,
        )
