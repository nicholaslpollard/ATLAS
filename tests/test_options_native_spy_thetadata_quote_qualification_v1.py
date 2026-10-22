from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    PilotQuoteSourceError, analyze_pilot_quote_surface, quote_design,
    run_pilot_quote_source_gate,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataError, ThetaDataResponse, _canonical_bytes,
)


def make_response(params, *, empty=False, right="both", future=False,
                  missing_put=False, stale_put=False):
    day = date(int(params["start_date"][:4]),
               int(params["start_date"][4:6]), int(params["start_date"][6:]))
    expiry = (day + timedelta(days=35)).isoformat()
    cutoff = datetime.fromisoformat(day.isoformat() + "T10:00:00-04:00")
    # Spring/winter qualification dates must retain the correct ET UTC offset.
    from zoneinfo import ZoneInfo
    cutoff = datetime.combine(day, datetime.min.time().replace(hour=10),
                              ZoneInfo("America/New_York"))
    rows = []
    if not empty:
        for role in (["CALL"] if missing_put else ["CALL", "PUT"]):
            t = cutoff + timedelta(seconds=1 if future else
                                   -45 if stale_put and role == "PUT" else -1)
            rows.append({
                "symbol": "SPY", "expiration": expiry, "strike": 500.0,
                "right": role if right == "both" else right,
                "timestamp": t.isoformat(),
                "bid_size": 5, "bid_exchange": 1, "bid": 5.0,
                "bid_condition": 0, "ask_size": 7, "ask_exchange": 1,
                "ask": 5.10, "ask_condition": 0,
            })
    r = tuple(rows)
    raw = _canonical_bytes(r)
    return ThetaDataResponse(
        http_status=200, rows=r, headers={}, response_bytes=len(raw),
        elapsed_seconds=0.1, raw_body=raw, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="1"*64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=empty,
    )


def test_full_pilot_design_reconstructs_frozen_24_plus_one_no_authority():
    plan = quote_design()
    calls = plan["quote_source_calls"]
    assert plan["quote_method_call_cap"] == 25
    assert len(calls) == 25
    assert [x["reason"] for x in calls[:3]] == [
        "2018_FIRST", "2018_MIDDLE", "2018_LAST"
    ]
    assert calls[-1]["repeat"] is True
    assert calls[-1]["query_fingerprint"] == calls[0]["query_fingerprint"]
    assert set(plan["years"]) == {str(y) for y in range(2018,2026)}
    assert all(c["params"]["right"] == "both"
               and c["params"]["time_of_day"] == "10:00:00.000"
               and c["params"]["max_dte"] == 45
               and c["params"]["strike_range"] == 2 for c in calls)
    assert plan["provider_requests"] == 0
    assert plan["source_accepted"] is False
    assert plan["run_authorized"] is False


def test_two_rights_common_strike_shape_without_historical_trade_authority():
    anchor = quote_design()["quote_source_calls"][0]
    summary = analyze_pilot_quote_surface(make_response(anchor["params"]), anchor)
    assert summary["status"] == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
    assert summary["call_rows"] == summary["put_rows"] == 1
    assert summary["common_30_45_dte_pairs"] == 1
    assert summary["clock_qualified_common_pairs"] == 1
    assert summary["pair_input_admissible"] is False


def test_partial_missing_and_older_quotes_do_not_become_valid_pairs():
    anchor = quote_design()["quote_source_calls"][8]
    only_call = analyze_pilot_quote_surface(
        make_response(anchor["params"], missing_put=True), anchor)
    assert only_call["common_30_45_dte_pairs"] == 0
    stale = analyze_pilot_quote_surface(
        make_response(anchor["params"], stale_put=True), anchor)
    assert stale["common_30_45_dte_pairs"] == 1
    assert stale["clock_qualified_common_pairs"] == 0


@pytest.mark.parametrize("variant,expected", [
    ("future", "FUTURE_OR_WRONG_SESSION_QUOTE"),
    ("duplicate", "DUPLICATE_EXACT_CONTRACT_RIGHT"),
    ("symbol", "UNEXPECTED_OPTION_ROOT"),
    ("naive", "UNQUALIFIED_NAIVE_QUOTE_CLOCK"),
    ("raw_drift", "QUOTE_RAW_RECEIPT_OR_SIZE_CHANGED"),
])
def test_malformed_source_cannot_qualify(variant, expected):
    anchor = quote_design()["quote_source_calls"][5]
    response = make_response(anchor["params"], future=variant=="future")
    from dataclasses import replace
    rows = list(response.rows)
    if variant == "duplicate":
        rows.append(dict(rows[0]))
    if variant == "symbol":
        rows[0] = {**rows[0], "symbol": "AAPL"}
    if variant == "naive":
        rows[0] = {**rows[0], "timestamp": "2020-01-01T09:59:59"}
    if variant == "raw_drift":
        response = replace(response, raw_body=b"wrong")
    else:
        canonical = _canonical_bytes(rows)
        response = replace(response, rows=tuple(rows), raw_body=canonical,
                           response_bytes=len(canonical))
    with pytest.raises((PilotQuoteSourceError, ValueError), match=expected):
        analyze_pilot_quote_surface(response, anchor)


def test_explicit_empty_and_implicit_empty_are_distinct():
    anchor = quote_design()["quote_source_calls"][0]
    from dataclasses import replace
    explicit = make_response(anchor["params"], empty=True)
    assert analyze_pilot_quote_surface(explicit, anchor)["status"] == "PROVIDER_EXPLICIT_NO_DATA"
    implicit = replace(explicit, explicit_no_data=False)
    assert analyze_pilot_quote_surface(implicit, anchor)["status"] == "EMPTY_RESPONSE_WITHOUT_EXPLICIT_NO_DATA"


class _Settings:
    def __init__(self, root):
        self.root = root
    def assert_external_storage_binding(self, category):
        assert category == "options"
    def resolved_path(self, value):
        return self.root / value


def test_25_anchored_receipts_and_repeat_are_not_source_acceptance(tmp_path):
    calls = []
    def reader(*, symbol, date_et, time_of_day_et, right, max_dte, strike_range):
        assert (symbol, time_of_day_et, right, max_dte, strike_range) == (
            "SPY", "10:00:00.000", "both", 45, 2)
        calls.append(date_et)
        return make_response({"start_date": date_et})
    report = run_pilot_quote_source_gate(
        _Settings(tmp_path), reader=reader,
        authorize_provider_reads=True, confirm_thetadata_standard=True,
        acknowledge_25_quote_method_call_cap=True,
    )
    assert len(calls) == 25 and calls[0] == calls[-1]
    assert report["requests_attempted"] == 25
    assert report["repeat_surface_equal"] is True
    assert report["repeat_sdk_normalized_raw_bytes_equal"] is True
    assert report["all_24_anchor_surfaces_observed"] is True
    assert report["raw_network_response_body_retained"] is False
    assert report["all_years_observed"] is True
    assert report["source_accepted"] is report["historical_fill_authority"] is False
    assert report["protected_outcomes_read"] == 0
    retained = json.loads(Path(report["report_path"]).read_text())
    assert retained["report_fingerprint"] == report["report_fingerprint"]
    assert len(retained["anchors"]) == 25


def test_entitlement_error_stops_without_retries_or_false_no_data(tmp_path):
    calls = []
    def reader(**kwargs):
        calls.append(kwargs)
        raise ThetaDataError("credential text MUST NOT APPEAR", http_status=403)
    report = run_pilot_quote_source_gate(
        _Settings(tmp_path), reader=reader,
        authorize_provider_reads=True, confirm_thetadata_standard=True,
        acknowledge_25_quote_method_call_cap=True,
    )
    assert len(calls) == 1
    assert report["requests_attempted"] == 1
    assert report["requests_not_attempted"] == 24
    assert report["status_counts"] == {"TRANSPORT_OR_ENTITLEMENT_ERROR":1}
    assert "credential text" not in Path(report["report_path"]).read_text()


@pytest.mark.parametrize("mutated_field,changed_value", [
    ("bid", 5.03), ("ask", 5.13), ("bid_size", 8),
    ("ask_size", 9), ("bid_exchange", 2), ("ask_condition", 3),
])
def test_changed_prices_sizes_or_quote_metadata_fail_exact_repeat(
    tmp_path, mutated_field, changed_value,
):
    from dataclasses import replace
    calls = []
    def reader(*, symbol, date_et, time_of_day_et, right, max_dte, strike_range):
        calls.append(date_et)
        response = make_response({"start_date": date_et})
        if len(calls) == 25:
            rows = list(response.rows)
            rows[0] = {**rows[0], mutated_field: changed_value}
            content = _canonical_bytes(rows)
            return replace(response, rows=tuple(rows), raw_body=content,
                           response_bytes=len(content))
        return response
    report = run_pilot_quote_source_gate(
        _Settings(tmp_path), reader=reader,
        authorize_provider_reads=True, confirm_thetadata_standard=True,
        acknowledge_25_quote_method_call_cap=True,
    )
    assert len(calls) == 25
    assert report["repeat_surface_equal"] is False
    assert report["repeat_sdk_normalized_raw_bytes_equal"] is False
    assert report["source_accepted"] is False


def test_equally_empty_first_and_last_are_not_successful_repeatability(tmp_path):
    calls = []
    def reader(*, symbol, date_et, time_of_day_et, right, max_dte, strike_range):
        calls.append(date_et)
        return make_response({"start_date": date_et},
                             empty=len(calls) in (1, 25))
    report = run_pilot_quote_source_gate(
        _Settings(tmp_path), reader=reader,
        authorize_provider_reads=True, confirm_thetadata_standard=True,
        acknowledge_25_quote_method_call_cap=True,
    )
    assert report["repeat_surface_equal"] is False
    assert report["repeat_sdk_normalized_raw_bytes_equal"] is False
    assert report["all_24_anchor_surfaces_observed"] is False
    assert report["source_accepted"] is False


@pytest.mark.parametrize("flags", [
    {},
    {"authorize_provider_reads": True},
    {"confirm_thetadata_standard": True},
    {"acknowledge_25_quote_method_call_cap": True},
    {"authorize_provider_reads": True, "confirm_thetadata_standard": True},
    {"authorize_provider_reads": True, "acknowledge_25_quote_method_call_cap": True},
    {"confirm_thetadata_standard": True, "acknowledge_25_quote_method_call_cap": True},
])
def test_direct_python_cannot_bypass_three_paid_read_authorizations(tmp_path, flags):
    calls = []
    def reader(**kwargs):
        calls.append(kwargs)
        raise AssertionError("provider called without authorization")
    with pytest.raises(PilotQuoteSourceError, match="NOT_EXPLICITLY_AUTHORIZED"):
        run_pilot_quote_source_gate(_Settings(tmp_path), reader=reader, **flags)
    assert calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("form", ["script", "module"])
def test_default_cli_is_provider_free_in_both_invocations(form):
    root = Path(__file__).resolve().parents[1]
    p = "scripts/qualify_options_native_spy_thetadata_quotes_v1.py"
    cmd = [sys.executable, str(root / p)] if form == "script" else [
        sys.executable, "-m", "scripts.qualify_options_native_spy_thetadata_quotes_v1"
    ]
    done = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                          timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    assert "DESIGN_ONLY_ZERO_PROVIDER_REQUESTS" in done.stdout
    gated = subprocess.run([*cmd, "--confirm-thetadata-standard"], cwd=root,
                           capture_output=True, text=True, timeout=30, check=False)
    assert gated.returncode == 2
    assert "BLOCKED_PARTIAL_PROVIDER_AUTHORIZATION" in gated.stdout
