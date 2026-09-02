from __future__ import annotations

from datetime import date

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
    parse_sec_terminal_transaction_v2_certified,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_REPAIR_V3_SEC_ALLOWED_FORMS,
    LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS,
    LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
    _filtered_sec_rows_v3,
    _report_fingerprint_v3,
    lit02_repair_v3_source_expansion_fingerprint,
    lit02_repair_v3_source_expansion_payload,
)


def test_v3_source_expansion_is_frozen_to_two_final_transaction_amendment_forms() -> None:
    payload = lit02_repair_v3_source_expansion_payload()
    assert payload["contract_version"] == LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT
    assert payload["sec_allowed_forms"] == ["SC 13E3/A", "SC TO-T/A"]
    assert payload["economic_paths_changed"] is False
    assert payload["required_source_coverage"] == 1.0
    assert payload["economic_outcome_values_allowed"] is False
    assert payload["new_price_or_return_reads_allowed"] is False
    assert payload["protected_reads_allowed"] is False
    assert payload["ticker_specific_exceptions_allowed"] is False
    assert payload["parser_certification"] == LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION


def test_v3_source_expansion_fingerprint_is_deterministic() -> None:
    assert lit02_repair_v3_source_expansion_fingerprint() == lit02_repair_v3_source_expansion_fingerprint()
    assert len(lit02_repair_v3_source_expansion_fingerprint()) == 64


def test_v3_excludes_proxy_registration_delisting_and_nonfinal_tender_forms() -> None:
    for form in ("DEFM14A", "PREM14A", "S-4", "F-4", "424B3", "425", "25-NSE", "SC TO-T"):
        assert form in LIT02_REPAIR_V3_SEC_EXPLICITLY_EXCLUDED_FORMS
        assert form not in LIT02_REPAIR_V3_SEC_ALLOWED_FORMS


def test_v3_filter_admits_only_sc_to_t_a_and_sc_13e3_a_in_window() -> None:
    rows = [
        {
            "accessionNumber": "0000000001-24-000001",
            "filingDate": "2024-06-10",
            "form": "SC TO-T/A",
            "items": "",
            "primaryDocument": "sctota.htm",
        },
        {
            "accessionNumber": "0000000001-24-000002",
            "filingDate": "2024-06-11",
            "form": "SC 13E3/A",
            "items": "",
            "primaryDocument": "sc13e3a.htm",
        },
        {
            "accessionNumber": "0000000001-24-000003",
            "filingDate": "2024-06-12",
            "form": "DEFM14A",
            "items": "",
            "primaryDocument": "proxy.htm",
        },
        {
            "accessionNumber": "0000000001-24-000004",
            "filingDate": "2024-06-13",
            "form": "25-NSE",
            "items": "",
            "primaryDocument": "form25.xml",
        },
        {
            "accessionNumber": "0000000001-23-000005",
            "filingDate": "2023-01-01",
            "form": "SC 13E3/A",
            "items": "",
            "primaryDocument": "old.htm",
        },
    ]
    filtered = _filtered_sec_rows_v3(
        rows,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 7, 1),
    )
    assert [item["form"] for item in filtered] == ["SC TO-T/A", "SC 13E3/A"]
    assert [item["accession_number"] for item in filtered] == [
        "0000000001-24-000001",
        "0000000001-24-000002",
    ]


def test_final_tender_amendment_with_completed_back_end_merger_resolves_cash_terminal() -> None:
    text = """
    SCHEDULE TO (Amendment No. 5). Following consummation of the Offer, the
    remaining conditions to the Merger were satisfied. On May 11, 2026, Parent
    completed the acquisition of Kezar through the merger of Merger Sub with and
    into Kezar, with Kezar continuing as the surviving corporation. At the
    Effective Time, each issued and outstanding Share not tendered into the Offer
    was automatically converted into the right to receive $1.10 in cash per share,
    without interest. The Shares ceased to trade on Nasdaq on May 11, 2026.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2026, 5, 29),
        historical_ticker="KZR",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["effective_date"] == "2026-05-11"
    assert result["cash_per_share"] == 1.10


def test_final_13e3_amendment_with_effective_merger_resolves_cash_terminal() -> None:
    text = """
    This Final Amendment is being filed pursuant to Rule 13e-3(d)(3) to report
    the results of the transaction. On July 1, 2021, the Company completed the
    previously announced merger of Merger Sub with and into the Company. The
    merger became effective on July 1, 2021. At the Effective Time, each issued
    and outstanding common share was converted into the right to receive $35.00
    per common share in cash, without interest.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2021, 7, 30),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] == "READY"
    assert result["path_id"] == "TERMINAL_CASH"
    assert result["effective_date"] == "2021-07-01"
    assert result["cash_per_share"] == 35.0


def test_tender_offer_terms_without_executed_merger_do_not_create_terminal_authority() -> None:
    text = """
    Purchaser is offering to purchase all outstanding Shares for $27.00 per Share
    in cash. The Offer is expected to expire on June 10, 2026. Subject to the
    satisfaction of the conditions in the Merger Agreement, Purchaser intends to
    complete the Merger as promptly as practicable after the Offer. If the Merger
    is completed, each remaining Share will be converted into the right to receive
    $27.00 in cash per share.
    """
    result = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=date(2026, 6, 30),
        historical_ticker="AAA",
    )
    assert result is not None
    assert result["status"] in {"INCOMPLETE", "CONFLICT"}
    assert result.get("path_id") != "TERMINAL_CASH"


def test_v3_report_fingerprint_ignores_only_transport_counters() -> None:
    base = {
        "status": "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE",
        "source_metadata_provider_reads": 10,
        "massive_source_metadata_reads": 2,
        "sec_source_metadata_reads": 8,
        "cached_case_manifests_reused": 0,
        "resolved_cases": 100,
        "unresolved_cases": 99,
        "economic_outcome_values_read": 0,
    }
    changed_transport = {
        **base,
        "source_metadata_provider_reads": 100,
        "massive_source_metadata_reads": 20,
        "sec_source_metadata_reads": 80,
        "cached_case_manifests_reused": 50,
    }
    changed_science = {**base, "resolved_cases": 101, "unresolved_cases": 98}
    assert _report_fingerprint_v3(base) == _report_fingerprint_v3(changed_transport)
    assert _report_fingerprint_v3(base) != _report_fingerprint_v3(changed_science)
