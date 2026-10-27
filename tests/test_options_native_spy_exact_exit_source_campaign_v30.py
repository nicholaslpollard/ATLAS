from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_development_clock_coverage_v1 import frozen_clock_demand
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT as V29_CONTRACT, SOURCE_PREVIEW,
)
from packages.data.options_native_spy_exact_exit_source_campaign_v30 import (
    CONTRACT, ExactExitSourceError, _state, load_exact_exit_plan,
    preview_exact_exit_campaign, run_exact_exit_campaign,
    _verify_v29_wrapped_fingerprint,
)
from packages.providers.thetadata import client
from packages.providers.thetadata.client import (
    ThetaDataResponse, ThetaDataError, _canonical_bytes,
    TARGET_LIBRARY_VERSION,
)

Q = {
    "symbol": "SPY", "date_et": "2025-01-07",
    "time_of_day_et": "10:00:00.000",
    "expiration": "2025-02-14", "strike": "100",
    "right": "call",
}
QID = _fingerprint({
    "provider": "thetadata", "method": "option_at_time_quote", "kwargs": Q,
})


def quote():
    return {
        "symbol": "SPY", "expiration": Q["expiration"], "strike": 100.0,
        "right": "call", "timestamp": "2025-01-07T09:59:55-05:00",
        "bid": 1.0, "ask": 1.1, "bid_size": 2, "ask_size": 1,
        "bid_exchange": 3, "ask_exchange": 3,
        "bid_condition": 0, "ask_condition": 0,
    }


def good_response(*, rows=None, explicit=False):
    value = [] if rows is None else rows
    body = _canonical_bytes(value)
    return ThetaDataResponse(
        http_status=200, rows=tuple(value), headers={},
        response_bytes=len(body), elapsed_seconds=0.01, raw_body=body,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="a" * 64,
        explicit_no_data=explicit,
    )


def preview_plan():
    review = {
        "hold_sessions": 1, "session_et": Q["date_et"],
        "missing_exact_rights": ["call"],
        "original_exit_source_state": "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
    }
    frozen, _ = frozen_clock_demand()
    cases = [{
        "date_et": row["decision_date"],
        "status": "RESEARCH_IDENTITY_NOT_AVAILABLE",
    } for row in frozen["cases"] if row["decision_date"] != "2025-01-06"]
    assert len(cases) == 410
    cases.append({
        "date_et": "2025-01-06", "status": "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY",
        "selected_expiration": Q["expiration"], "selected_strike": Q["strike"],
        "review_results": [review],
    })
    demand = [{
        "query_id": QID, "sdk_method": "option_at_time_quote", "sdk_kwargs": Q,
        "request_state": SOURCE_PREVIEW, "case_date": "2025-01-06",
        "hold_sessions": 1, "source_original_exit_query_id": _exit_at_time_query(date(2025, 1, 7))["query_id"],
        "entry_spot_unqualified": True,
        "source_response_absence_not_market_absence": True,
    }]
    report = {
        "contract": V29_CONTRACT, "original_entry_clocks": 411,
        "source_quote_selection_used_future_prices": False,
        "entry_physical_spot_historical_availability_qualified": False,
        "historical_options_fill_authority": False,
        "provider_requests": 0, "broker_requests": 0,
        "protected_2026_outcomes_read": 0,
        "missing_exact_contract_right_requests": demand,
        "missing_exact_contract_right_request_count": 1,
        "cases": cases,
    }
    # Real V29 CLI wraps the already-fingerprinted V29 evaluator inside V26.
    # Retain this exact two-layer original-source report convention.
    report["fingerprint"] = _fingerprint(report)
    wrapped = {
        "contract": "atlas-source-linked-spy-quote-pair-diagnostic-v26",
        "status": "RETROSPECTIVE_SOURCE_MATCH_DIAGNOSTIC_ONLY",
        "original_411_entry_plan": 411,
        "distinct_new_exit_request_plan": 1570,
        "observed_source_identities_loaded": 1981,
        "source_plan_fingerprint": "a" * 64,
        "note": "Unqualified historical quote diagnostic",
        "pricing": "10:00 quote observation only; no 10:01 trade fills",
        "fee_grid_is_model_assumption": True,
        "provider_requests": 0, "broker_requests": 0,
        "simulations_run": 0, "account_pnl_reported": False,
        "historical_execution_qualified": False,
        "protected_outcomes_read": 0, "strategy_promotion": False,
        **report,
    }
    wrapped["fingerprint"] = _fingerprint(wrapped)
    return wrapped


class Settings:
    def __init__(self, root):
        self.root = root

    def assert_external_storage_binding(self, name):
        assert name == "options"

    def resolved_path(self, value):
        return self.root / value


class Meter:
    def __init__(self, settings, storage_reader):
        self.full_audits = 1

    def allow_next(self):
        return True


def test_exact_shared_auth_batch_retains_exact_contract_scope(monkeypatch):
    requests = []
    class Worker:
        def request(self, method, kwargs):
            requests.append((method, kwargs))
            return {
                "shared_authenticated_session": True,
                "results": [{
                    "ok": True, "rows": [quote()], "explicit_no_data": False,
                    "library_version": TARGET_LIBRARY_VERSION,
                    "environment_fingerprint": "a" * 64,
                }],
            }
    monkeypatch.setattr(client, "_worker", lambda: Worker())
    responses = client.option_at_time_quote_exact_shared_session_batch([Q])
    assert len(responses) == 1 and isinstance(responses[0], ThetaDataResponse)
    assert requests[0][0] == "batch_option_at_time_quote_shared_session"
    kwargs = requests[0][1]["queries"][0]
    assert kwargs["expiration"] == "2025-02-14"
    assert kwargs["strike"] == "100"
    assert kwargs["right"] == "call"
    assert "strike_range" not in kwargs
    for bad in (dict(Q, strike="1E+2"), dict(Q, right="both"),
                dict(Q, time_of_day_et="10:01:00.000"),
                dict(Q, expiration="2024-12-31"), dict(Q, symbol="QQQ")):
        with pytest.raises(ValueError):
            client.option_at_time_quote_exact_shared_session_batch([bad])
    assert len(requests) == 1


def test_plan_bound_to_original_entry_choice_and_exact_missing_right(tmp_path):
    import json
    plan = preview_plan()
    path = tmp_path / "v29.json"
    path.write_text(json.dumps(plan))
    assert _verify_v29_wrapped_fingerprint(plan)
    assert load_exact_exit_plan(path)["fingerprint"] == plan["fingerprint"]
    edited = dict(plan)
    edited["missing_exact_contract_right_requests"] = [{
        **plan["missing_exact_contract_right_requests"][0],
        "sdk_kwargs": dict(Q, right="put"),
    }]
    edited["fingerprint"] = _fingerprint(edited)
    path.write_text(json.dumps(edited))
    with pytest.raises(ExactExitSourceError):
        load_exact_exit_plan(path)


def test_immutable_paid_single_exact_receipt_and_idempotent_resume(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    assert preview_exact_exit_campaign(settings, plan)["remaining_unattempted"] == 1
    authenticated = []
    batches = []

    def reader(queries):
        batches.append(queries)
        return [good_response(rows=[quote()])]

    result = run_exact_exit_campaign(
        settings, plan, batch_reader=reader,
        authenticator=lambda: authenticated.append(True),
        meter_factory=Meter, storage_reader=lambda *_args: None,
    )
    assert authenticated == [True]
    assert batches == [[Q]]
    assert result["provider_requests_this_run"] == 1
    assert result["archived_this_run"] == 1
    assert result["remaining"] == 0
    assert result["states"]["RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC"] == 1
    assert _state(settings, plan["missing_exact_contract_right_requests"][0], plan["fingerprint"]) == (
        "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC"
    )

    # Resuming does not even construct shared authentication or repeat a GET.
    second = run_exact_exit_campaign(
        settings, plan, batch_reader=lambda q: (_ for _ in ()).throw(AssertionError("retry")),
        authenticator=lambda: (_ for _ in ()).throw(AssertionError("reauth")),
        meter_factory=Meter,
    )
    assert second["provider_requests_this_run"] == 0
    assert second["remaining"] == 0


def test_explicit_no_data_is_terminal_not_retryable(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    result = run_exact_exit_campaign(
        settings, plan, batch_reader=lambda q: [good_response(explicit=True)],
        authenticator=lambda: None, meter_factory=Meter,
    )
    assert result["no_data_this_run"] == 1
    assert result["states"]["EXPLICIT_NO_DATA_SOURCE_ONLY"] == 1
    assert result["remaining"] == 0


def test_ambiguous_shared_session_transport_leaves_started_without_same_id_retry(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    def error_batch(q):
        raise RuntimeError("simulated worker connection loss")
    result = run_exact_exit_campaign(
        settings, plan, batch_reader=error_batch, authenticator=lambda: None,
        meter_factory=Meter,
    )
    assert result["stop_reason"] == "AMBIGUOUS_SHARED_BATCH_NO_SAME_QUERY_RETRY"
    state = _state(settings, plan["missing_exact_contract_right_requests"][0], plan["fingerprint"])
    assert state == "UNCERTAIN_PREVIOUS_DISPATCH_NO_RETRY"
    assert preview_exact_exit_campaign(settings, plan)["remaining_unattempted"] == 0
    result2 = run_exact_exit_campaign(
        settings, plan, batch_reader=error_batch,
        authenticator=lambda: (_ for _ in ()).throw(AssertionError("retry")),
        meter_factory=Meter,
    )
    assert result2["provider_requests_this_run"] == 0


def test_exact_provider_mismatched_original_contract_is_archived_invalid_not_promoted(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    bad = dict(quote(), strike=101.0)
    result = run_exact_exit_campaign(
        settings, plan,
        batch_reader=lambda qs: [good_response(rows=[bad])],
        authenticator=lambda: None, meter_factory=Meter,
    )
    assert result["states"]["RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT"] == 1
    assert result["archived_this_run"] == 1
    assert result["source_promotion"] is False


def test_hard_sdk_authentication_failure_stops_and_keeps_terminal_error(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    err = ThetaDataError(
        "safe error", provider_error_type="_MultiThreadedRendezvous",
        provider_grpc_status="UNAUTHENTICATED",
    )
    result = run_exact_exit_campaign(
        settings, plan,
        batch_reader=lambda qs: [err],
        authenticator=lambda: None, meter_factory=Meter,
    )
    assert result["stop_reason"] == "HARD_PROVIDER_OR_REPEATED_SOURCE_SCHEMA_FAILURE"
    assert result["provider_failures_this_run"] == 1
    assert result["remaining"] == 0
    assert result["states"]["PROVIDER_OR_STORAGE_ERROR_NO_RETRY"] == 1


def test_zero_missing_rights_is_success_without_authentication(tmp_path):
    plan = preview_plan()
    plan["missing_exact_contract_right_requests"] = []
    plan["missing_exact_contract_right_request_count"] = 0
    plan["fingerprint"] = _fingerprint({
        k: v for k, v in plan.items() if k != "fingerprint"
    })
    result = run_exact_exit_campaign(
        Settings(tmp_path), plan,
        authenticator=lambda: (_ for _ in ()).throw(AssertionError("unneeded auth")),
        batch_reader=lambda q: (_ for _ in ()).throw(AssertionError("unneeded get")),
        meter_factory=Meter,
    )
    assert result["provider_requests_this_run"] == 0
    assert result["remaining"] == 0
    assert result["states"] == {}
    assert result["source_promotion"] is False



def test_v29_original_two_level_hash_rejects_tampering_without_rewriting_report():
    """A legitimate CLI-produced wrapper is different from a single digest."""
    original = preview_plan()
    assert _verify_v29_wrapped_fingerprint(original) is True
    assert original["fingerprint"] != _fingerprint({
        k: v for k, v in original.items() if k != "fingerprint"
    })
    tampered = dict(original)
    tampered["missing_exact_contract_right_request_count"] = 999
    assert _verify_v29_wrapped_fingerprint(tampered) is False
    forged_single_hash = dict(original)
    forged_single_hash["fingerprint"] = _fingerprint({
        k: v for k, v in original.items() if k != "fingerprint"
    })
    assert _verify_v29_wrapped_fingerprint(forged_single_hash) is False


def test_reject_unwrapped_v29_report_even_if_inner_fingerprint_valid(tmp_path):
    original = preview_plan()
    unwrapped = {
        k: v for k, v in original.items()
        if k not in {
            "original_411_entry_plan", "distinct_new_exit_request_plan",
            "observed_source_identities_loaded", "source_plan_fingerprint",
            "note", "pricing", "fee_grid_is_model_assumption",
            "simulations_run", "account_pnl_reported",
            "historical_execution_qualified", "protected_outcomes_read",
            "strategy_promotion",
        }
    }
    unwrapped["fingerprint"] = _fingerprint({
        k: v for k, v in unwrapped.items() if k != "fingerprint"
    })
    report = tmp_path / "unwrapped_v29.json"
    import json
    report.write_text(json.dumps(unwrapped), encoding="utf-8")
    with pytest.raises(ExactExitSourceError, match="FROZEN_PLAN_FINGERPRINT"):
        load_exact_exit_plan(report)



def test_extra_dte_contracts_are_archived_losslessly_but_local_exact_right_matches(tmp_path):
    """Extra returned expirations must not veto a uniquely matched exact quote."""
    settings, plan = Settings(tmp_path), preview_plan()
    extra_expiry = dict(quote(), expiration="2025-04-18", strike=105.0)
    result = run_exact_exit_campaign(
        settings, plan,
        batch_reader=lambda qs: [good_response(rows=[extra_expiry, quote()])],
        authenticator=lambda: None, meter_factory=Meter,
    )
    assert result["states"]["RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC"] == 1
    assert result["archived_this_run"] == 1
    row = plan["missing_exact_contract_right_requests"][0]
    from packages.data.options_native_spy_exact_exit_source_campaign_v30 import (
        _read_receipt, _path,
    )
    terminal = _read_receipt(settings, row, plan["fingerprint"], "terminal")
    assert terminal["archive"]["observed_rows"] == 2
    assert _path(settings, row["query_id"], "sources").is_file()
    assert result["source_promotion"] is False
    assert result["historical_account_replay"] is False


def test_duplicate_exact_right_never_admitted_even_if_other_contracts_returned(tmp_path):
    settings, plan = Settings(tmp_path), preview_plan()
    result = run_exact_exit_campaign(
        settings, plan,
        batch_reader=lambda qs: [good_response(rows=[quote(), quote()])],
        authenticator=lambda: None, meter_factory=Meter,
    )
    assert result["states"]["RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT"] == 1
    assert result["archived_this_run"] == 1
    assert result["remaining"] == 0
