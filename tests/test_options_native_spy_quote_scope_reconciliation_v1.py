from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.data.options_native_spy_quote_scope_reconciliation_v1 import (
    SourceProjectionError, inspect_explicit_dte_projection,
)
from packages.data.options_native_spy_standard_canary_v1 import canary_design
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)


def sample(*, extra_dte: int = 67, after_clock: bool = False,
           duplicated: bool = False, bad_bid: bool = False):
    day = date(2025, 6, 9)
    decision = datetime.combine(
        day, datetime.min.time().replace(hour=10),
        ZoneInfo("America/New_York"),
    )
    rows = []
    for dte in (32, 39, extra_dte):
        for side in ("CALL", "PUT"):
            row = {
                "symbol": "SPY", "expiration": (day + timedelta(days=dte)).isoformat(),
                "strike": 600.0, "right": side,
                "timestamp": (
                    decision + timedelta(milliseconds=10)
                    if after_clock and dte == extra_dte
                    else decision - timedelta(milliseconds=5)
                ).isoformat(),
                "bid": 4.95, "ask": 5.00, "bid_size": 2, "ask_size": 3,
                "bid_exchange": 1, "ask_exchange": 1,
                "bid_condition": 0, "ask_condition": 0,
            }
            if bad_bid and dte == extra_dte:
                row["bid"] = 6.0
            rows.append(row)
    if duplicated:
        rows.append(dict(rows[-1]))
    raw = _canonical_bytes(rows)
    response = ThetaDataResponse(
        http_status=200, rows=tuple(rows), headers={},
        response_bytes=len(raw), elapsed_seconds=0,
        raw_body=raw, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="b" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )
    return response


def test_projection_only_reports_common_pairs_and_preserves_original():
    req = canary_design()["selected_anchor"]
    response = sample()
    before = response.raw_body
    report = inspect_explicit_dte_projection(response, req)
    assert report["full_original_rows"] == 6
    assert report["within_requested_dte_rows"] == 4
    assert report["beyond_requested_dte_rows"] == 2
    assert report["over_max_dte_by_calendar_days"] == {67: 2}
    assert report["within_requested_dte_calls"] == 2
    assert report["within_requested_dte_puts"] == 2
    assert report["out_of_scope_calls"] == 1
    assert report["out_of_scope_puts"] == 1
    q = report["projected_validator_diagnostic"]
    assert q["common_30_45_dte_pairs"] == 2
    assert q["clock_qualified_common_pairs"] == 2
    assert report["full_original_sdk_sha256"] != report["explicit_projection_sha256"]
    assert report["source_accepted"] is False
    assert report["pair_input_admissible"] is False
    assert report["historical_replay_authority"] is False
    assert report["provider_requests"] == report["protected_outcomes_read"] == 0
    assert response.raw_body == before and len(response.rows) == 6


@pytest.mark.parametrize("value", [46, 67, 921])
def test_only_calendar_dtes_over_45_are_visible_exclusions(value):
    req = canary_design()["selected_anchor"]
    report = inspect_explicit_dte_projection(sample(extra_dte=value), req)
    assert report["over_max_dte_by_calendar_days"] == {value: 2}
    assert report["within_requested_dte_rows"] == 4


@pytest.mark.parametrize("mutation,reason", [
    ({"max_dte": 921}, "ORIGINAL_QUOTE_QUERY_SCOPE_CHANGED"),
    ({"right": "call"}, "ORIGINAL_QUOTE_QUERY_SCOPE_CHANGED"),
    ({"time_of_day": "09:35:00.000"}, "ORIGINAL_QUOTE_QUERY_SCOPE_CHANGED"),
])
def test_original_request_cannot_be_relaxed_to_make_source_pass(mutation,reason):
    q = canary_design()["selected_anchor"]
    req = {**q, "params": {**q["params"], **mutation}}
    with pytest.raises(SourceProjectionError, match=reason):
        inspect_explicit_dte_projection(sample(),req)


@pytest.mark.parametrize("kwargs,expected", [
    ({"after_clock": True}, "ORIGINAL_FUTURE_OR_WRONG_DATE_QUOTE"),
    ({"duplicated": True}, "ORIGINAL_DUPLICATE_OPTION_IDENTITY"),
    ({"bad_bid": True}, "ORIGINAL_CROSSED_QUOTE"),
])
def test_outside_dte_rows_are_not_silently_exempt_from_quality_rules(kwargs,expected):
    with pytest.raises(SourceProjectionError, match=expected):
        inspect_explicit_dte_projection(
            sample(**kwargs),canary_design()["selected_anchor"]
        )


def test_tampered_raw_canonical_evidence_blocks_projection():
    good = sample()
    bad = replace(good,raw_body=good.raw_body+b" ")
    with pytest.raises(SourceProjectionError,match="ORIGINAL_SDK_SOURCE_RECEIPT_UNQUALIFIED"):
        inspect_explicit_dte_projection(bad,canary_design()["selected_anchor"])
