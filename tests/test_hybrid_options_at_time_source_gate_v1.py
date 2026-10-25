from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import hybrid_options_at_time_source_gate_v1 as v10
from packages.data.hybrid_options_frozen_research_demand_v1 import (
    build_frozen_research_demand,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import inspect_hybrid_options_at_time_source_gate_v1 as cli


@pytest.fixture(scope="module")
def spy_row():
    report = build_frozen_research_demand()
    return next(x for x in report["requests"]
                if x["date_et"] == "2025-06-09")


def quote(*, day="2025-06-09", expiration="2025-07-11",
          right="call", symbol="SPY", stamp="2025-06-09T09:59:55-04:00",
          bid=3.0, ask=3.1, strike=600.0):
    return {
        "symbol": symbol, "expiration": expiration, "strike": strike,
        "right": right, "timestamp": stamp, "bid": bid, "ask": ask,
        "bid_size": 4, "ask_size": 8,
        "bid_exchange": 1, "ask_exchange": 2,
        "bid_condition": 0, "ask_condition": 0,
    }


def response(rows, *, explicit_no_data=False):
    rows = tuple(rows)
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={},
        response_bytes=len(raw), raw_body=raw, elapsed_seconds=0,
        transport=TRANSPORT, library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="d" * 64,
        evidence_encoding=EVIDENCE_ENCODING,
        explicit_no_data=explicit_no_data,
    )


def test_exact_spy_1000_mapping_does_not_call_sdk(spy_row):
    kwargs = v10.validate_exact_request(spy_row)
    assert kwargs == {
        "symbol": "SPY", "date_et": "2025-06-09",
        "time_of_day_et": "10:00:00.000",
        "right": "both", "max_dte": 45, "strike_range": 2,
    }
    assert v10.BLOCKED_SDK_DTE_STATUS.endswith("UNPROVEN")


def test_in_scope_call_put_diagnostic_no_promotion(spy_row):
    original = quote()
    put = quote(right="put")
    report = v10.diagnose_at_time_response(
        spy_row, response((original, put)),
    )
    assert report["status"] == "IN_SCOPE_OBSERVED_NOT_EXECUTABLE"
    assert report["full_original_row_count"] == 2
    assert report["within_requested_dte_rows"] == 2
    assert report["outside_requested_dte_rows"] == 0
    assert report["positive_two_sided_displayed_size_rows"] == 2
    assert report["original_response_is_complete_chain_proven"] is False
    assert report["source_promoted"] is False
    assert report["paid_at_time_provider_calls_authorized"] is False
    assert report["simulator_ready"] is False
    assert report["provider_requests"] == 0
    assert report["diagnostic_fingerprint"] == v10._fingerprint({
        k: v for k, v in report.items() if k != "diagnostic_fingerprint"
    })


def test_over_dte_retains_full_canonical_evidence(spy_row):
    original = quote()
    farther = quote(expiration="2025-09-19", strike=620.0)
    source = response((original, farther))
    diag = v10.diagnose_at_time_response(spy_row, source)
    assert diag["status"] == "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION"
    assert diag["within_requested_dte_rows"] == 1
    assert diag["outside_requested_dte_rows"] == 1
    assert diag["full_original_row_count"] == 2
    assert diag["original_response_replaced_or_filtered"] is False
    assert diag["original_source_bytes"] == len(source.raw_body)


@pytest.mark.parametrize("bad,expected", [
    (quote(stamp="2025-06-09T10:00:01-04:00"),
     "FUTURE_OR_OTHER_DAY"),
    (quote(stamp="2025-06-08T10:00:00-04:00"),
     "FUTURE_OR_OTHER_DAY"),
    (quote(stamp="2025-06-09T09:59:55"),
     "naive"),
    (quote(symbol="QQQ"), "OPTION_ROOT"),
    (quote(right="invalid"), "OPTION_RIGHT"),
    (quote(expiration="2025-05-30"), "EXPIRED_CONTRACT"),
    (quote(strike=0), "OPTION_STRIKE"),
    (quote(bid=5.0, ask=3.0), "CROSSED"),
])
def test_invalid_rows_fail_closed(spy_row, bad, expected):
    with pytest.raises(ValueError):
        v10.diagnose_at_time_response(spy_row, response([bad]))


def test_duplicate_expiration_strike_right_fails(spy_row):
    rows = [quote(), deepcopy(quote())]
    with pytest.raises(v10.HybridAtTimeSourceGateError, match="DUPLICATE"):
        v10.diagnose_at_time_response(spy_row, response(rows))


def test_missing_field_and_bad_source_receipt_fail(spy_row):
    item = quote()
    del item["bid_exchange"]
    with pytest.raises(v10.HybridAtTimeSourceGateError, match="FIELDS_MISSING"):
        v10.diagnose_at_time_response(spy_row, response([item]))
    valid = response([quote()])
    object.__setattr__(valid, "raw_body", b"tampered")
    with pytest.raises(v10.HybridAtTimeSourceGateError, match="CANONICAL"):
        v10.diagnose_at_time_response(spy_row, valid)


def test_explicit_no_data_and_empty_response_separate(spy_row):
    assert v10.diagnose_at_time_response(
        spy_row, response([], explicit_no_data=True),
    )["status"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
    assert v10.diagnose_at_time_response(
        spy_row, response([]),
    )["status"] == "EMPTY_RESPONSE_NOT_COVERAGE"
    with pytest.raises(v10.HybridAtTimeSourceGateError):
        v10.diagnose_at_time_response(
            spy_row, response([quote()], explicit_no_data=True),
        )


@pytest.mark.parametrize("key,value", [
    ("query_id", "a" * 64),
    ("decision_clock_et", "09:35:00.000"),
    ("source_role", "0935_CALL_ENTRY_DISCOVERY"),
    ("exact_adapter", "ALREADY_ENABLED"),
    ("simulator_ready", True),
])
def test_mutated_v9_row_blocks_adapter(spy_row, key, value):
    item = deepcopy(spy_row)
    item[key] = value
    with pytest.raises(v10.HybridAtTimeSourceGateError):
        v10.validate_exact_request(item)


def test_sdk_mapping_respects_at_time_call_only_when_original_sha_valid(spy_row):
    item = deepcopy(spy_row)
    item["params"]["right"] = "call"
    item["right"] = "call"
    with pytest.raises(v10.HybridAtTimeSourceGateError):
        v10.validate_exact_request(item)


def test_v10_0935_exact_mapping(candidate_plan=None):
    # Small directly synthesized V9 entry exercises exact 09:35 CALL request
    # shape without constructing an SDK client or altering the frozen plan.
    from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
    fp = "a" * 64
    data = {
        "endpoint": "/v3/option/at_time/quote",
        "params": {
            "symbol": "AAPL", "start_date": "20210301", "end_date": "20210301",
            "time_of_day": "09:35:00.000", "expiration": "*",
            "strike": "*", "right": "call", "max_dte": 75,
            "strike_range": None, "format": "json",
        },
    }
    row = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES", fp, fp,
        data, role="0935_CALL_ENTRY_DISCOVERY", anchor=True,
    )
    row["priority"] = 1
    assert v10.validate_exact_request(row) == {
        "symbol": "AAPL", "date_et": "2021-03-01",
        "time_of_day_et": "09:35:00.000",
        "right": "call", "max_dte": 75, "strike_range": None,
    }
    valid = quote(
        day="2021-03-01", symbol="AAPL", expiration="2021-04-16",
        stamp="2021-03-01T09:34:58-05:00",
    )
    diag = v10.diagnose_at_time_response(row, response([valid]))
    assert diag["status"] == "IN_SCOPE_OBSERVED_NOT_EXECUTABLE"
    with pytest.raises(v10.HybridAtTimeSourceGateError, match="OPTION_RIGHT"):
        v10.diagnose_at_time_response(
            row, response([quote(symbol="AAPL", right="put",
                  expiration="2021-04-16",
                  stamp="2021-03-01T09:34:58-05:00")]),
        )


def test_original_saved_canary_identity_matches_2025_frozen_plan(spy_row):
    assert v10.match_retained_spy_canary_to_v9(
        spy_row, original_query_fp=spy_row["origin_query_fingerprint"],
    )["status"] == "EXACT_RETAINED_SPY_CANARY_SOURCE_REPLAY_ONLY"
    with pytest.raises(v10.HybridAtTimeSourceGateError, match="LINEAGE"):
        v10.match_retained_spy_canary_to_v9(
            spy_row, original_query_fp="0" * 64,
        )


def test_cli_default_does_not_open_retained_source(tmp_path, monkeypatch, capsys):
    class FakeSettings:
        def assert_external_storage_binding(self, binding):
            assert binding == "options"
        def resolved_path(self, name):
            pytest.fail("Default V10 preview cannot inspect user files")
    monkeypatch.setattr(cli, "load_settings", lambda *_: FakeSettings())
    assert cli.main([]) == 0
    output = capsys.readouterr().out
    assert "retained_source_replay=NOT_REQUESTED" in output
    assert "provider_requests=0" in output
    assert "source_promoted=False" in output


def test_cli_retained_source_replay_can_be_injected_without_provider(tmp_path, monkeypatch, capsys):
    class FakeSettings:
        def assert_external_storage_binding(self, binding):
            assert binding == "options"
    monkeypatch.setattr(cli, "load_settings", lambda *_: FakeSettings())
    monkeypatch.setattr(
        cli, "replay_retained_spy",
        lambda *_: {
            "full_rows": 264, "in_dte_rows": 120, "over_dte_rows": 144,
            "admission_status": "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION",
            "original_retained_sha256": "a" * 64,
            "diagnostic_fingerprint": "b" * 64,
        },
    )
    assert cli.main(["--replay-retained-spy"]) == 0
    assert "out_dte=144" in capsys.readouterr().out
