from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as CACHE_CONTRACT, _one_get, _path
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import _decode_snapshot_rows
from packages.simulation import retained_option_exit_source_audit_v1 as audit


def signed(value, field):
    value = copy.deepcopy(value)
    value.pop(field, None)
    value[field] = _fingerprint(value)
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def rebind(settings, binding, review, scenario):
    scenario = signed(scenario, "scenario_fingerprint")
    scenario_sha = save(settings.resolved_path(binding.scenario_path), scenario)
    review = copy.deepcopy(review)
    review.update(source_scenario_fingerprint=scenario["scenario_fingerprint"],
                  source_scenario_file_sha256=scenario_sha)
    review = signed(review, "report_fingerprint")
    review_sha = save(settings.resolved_path(binding.review_path), review)
    binding = replace(binding, review_sha256=review_sha, review_fingerprint=review["report_fingerprint"],
        scenario_sha256=scenario_sha, scenario_fingerprint=scenario["scenario_fingerprint"])
    return settings, binding, review, scenario


def fixture(tmp_path, *, bid_size=3, zero_volume=True, late_exact_absent=False, query_end="2021-12-18"):
    settings = SimpleNamespace(resolved_path=lambda path: tmp_path / path,
                               assert_external_storage_binding=lambda *_: None)
    cases, work = [], []
    for ticker, entry, exit_at, quote_at, units, volume, size in (
        ("ZERO", "2021-11-01T20:00:00+00:00", "2021-11-02T20:00:00+00:00",
         "2021-11-02T20:00:00+00:00", 5, 0 if zero_volume else 10, bid_size),
        ("EARLY", "2021-11-22T21:00:00+00:00", "2021-11-26T18:00:00+00:00",
         "2021-11-26T18:00:00+00:00", 2, 10, 20),
        ("LATE", "2021-11-22T21:00:00+00:00", "2021-11-26T18:00:00+00:00",
         "2021-11-26T21:00:00+00:00", 2, 0, 20),
    ):
        symbol = ticker + "211217C00100000"
        query = {"option_symbol": symbol, "from_inclusive": "2021-09-27", "to_exclusive": query_end}
        rid = _fingerprint({"contract": CACHE_CONTRACT, "query": query})
        ticket = {**query, "request_identity": rid}
        payload = {"s": "ok", "optionSymbol": [symbol, symbol],
            "updated": [int(datetime.fromisoformat(at).timestamp()) for at in (entry, quote_at)],
            "bid": [1, 2], "ask": [1.1, 2.1], "last": [1, 2],
            "bidSize": [20, size], "askSize": [20, 20], "volume": [10, volume],
            "openInterest": [100, 100], "underlyingPrice": [100, 101]}
        original = json.dumps(payload).encode()
        projection = _decode_snapshot_rows(original, ticket, 2)[1]
        if late_exact_absent and ticker == "ZERO":
            # A later-session row is present but cannot substitute for the exact exit.
            payload["updated"][1] = int(datetime.fromisoformat("2021-11-03T20:00:00+00:00").timestamp())
        raw = json.dumps(payload).encode()
        receipt = _one_get(settings, ticket, "synthetic-fixture", lambda *_: (200, raw, {
            "X-Api-Ratelimit-Consumed": "1", "X-Api-Ratelimit-Remaining": "999"}))
        source = {"physical_quote_request_identity": rid, "physical_quote_body_sha256": receipt["body_sha256"]}
        stock_exit = {"session_et": exit_at[:10], "disposition": "TIME"}
        cid = _fingerprint({"case": ticker})
        cases.append({"case_id": cid, "ticker": ticker, "economic_family_id": "fixture",
            "call": {"option_symbol": symbol, "entry": {"at_utc": entry, **source}},
            "stock_exit": stock_exit, "strategy_aligned_status": "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP",
            "strategy_exit_option_mark": {"session_et": projection["session_et"],
                "updated_at_utc": projection["updated_at_utc"], "bid_per_share": projection["bid"],
                **{key: projection[key] for key in ("two_sided", "positive_bid_size", "positive_reported_volume")}}})
        work.append({"case_id": cid, "ticker": ticker, "economic_family_id": "fixture",
            "option_symbol": symbol, "contracts": units, "expiration": "2021-12-17", "entry_at_utc": entry,
            "recorded_failed_exit_at_utc": exit_at, "recorded_stock_exit": stock_exit,
            "source_gap_reason": "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP", "recorded_entry_source_binding": source})
    scenario = {"contract": audit.SCENARIO_CONTRACT,
        "status": "MODELED_CONTINUOUS_DYNAMIC_EXIT_V2_EOD_CALL_SCENARIO", "original_case_denominator": 3,
        "cases": cases, "provider_requests": 0, "protected_2026_outcomes_read": 0, "historical_fills_verified": 0,
        "independent_occ_deliverable_multiplier_verified": 0,
        "historical_account_pnl_authority": False, "strategy_evidence_authority": False,
        "future_option_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True}
    review = {"contract": audit.REVIEW_CONTRACT,
        "status": "COMPLETE_RETAINED_LEDGER_REVIEW_UNRESOLVED_EVIDENCE_DEMAND",
        "source_replay_fingerprint": "b" * 64, "unresolved_positions": work, "unresolved": 3,
        "original_cases": 3, "provider_requests": 0, "broker_requests": 0, "raw_source_files_read": 0,
        "simulations_run": 0, "original_artifacts_modified": False, "source_reaccepted": False,
        "strategy_promotion": False, "historical_account_return_authority": False, "paper": False, "live": False,
        "equity": None, "total_return": None, "terminal_valuation_clock": None}
    binding = replace(audit.DEFAULT_BINDING,
        review_path="data/research/retained_option_account_review_v1/fixture.json",
        scenario_path="data/options/derived/fixture.json", replay_fingerprint="b" * 64,
        scenario_cases=3, unresolved_positions=3, unresolved_contracts=9)
    return rebind(settings, binding, review, scenario)


def row(report, ticker):
    return next(item for item in report["positions"] if item["ticker"] == ticker)


def cache_paths(settings, review, ticker="ZERO"):
    work = next(item for item in review["unresolved_positions"] if item["ticker"] == ticker)
    return _path(settings, {"request_identity": work["recorded_entry_source_binding"]["physical_quote_request_identity"]})


def test_source_facts_separate_volume_capacity_and_early_close_without_replay(tmp_path):
    settings, binding, review, _ = fixture(tmp_path)
    originals = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    report = audit.audit_retained_option_exit_sources(settings, binding=binding)
    assert report["position_count"] == report["raw_option_files_read"] == report["verified_position_sources"] == 3
    assert report["contract_count"] == 9
    assert report["legacy_failure_counts_nonexclusive"] == {"LEGACY_REQUIRES_1600_ET": 1, "REPORTED_VOLUME_NOT_POSITIVE": 2}
    assert row(report, "ZERO")["reported_bid_size_covers_position"] is False
    assert row(report, "EARLY")["snapshot_clock_relation"] == "AT_RECORDED_EXIT"
    assert row(report, "EARLY")["calendar_close_rejected_by_legacy_1600_rule"] is True
    assert row(report, "LATE")["snapshot_clock_relation"] == "AFTER_RECORDED_EXIT"
    assert row(report, "LATE")["quote_snapshot_not_fill"]["updated_is_1600_et"] is True
    assert report["snapshot_clock_relations"] == {"AFTER_RECORDED_EXIT": 1, "AT_RECORDED_EXIT": 2}
    assert report["retained_classification_disagreements"] == 0
    assert report["equity"] is report["total_return"] is report["terminal_valuation_clock"] is None
    for key in ("provider_requests", "broker_requests", "simulations_run", "raw_stock_files_read"):
        assert report[key] == 0
    for key in ("later_quote_search_performed", "source_reaccepted", "historical_fill_authority",
                "option_trading_hours_qualified", "source_publication_availability_verified",
                "exit_policy_changed", "fee_policy_changed", "settlement_inferred", "capital_released",
                "original_artifacts_modified", "strategy_promotion", "paper", "live"):
        assert report[key] is False
    assert {path: path.read_bytes() for path in originals} == originals


@pytest.mark.parametrize("size,coverage,unknown", [(0, False, 0), (1, False, 0), (5, True, 0), (None, None, 1)])
def test_reported_positive_size_is_distinct_from_whole_position_capacity(tmp_path, size, coverage, unknown):
    settings, binding, _, _ = fixture(tmp_path, bid_size=size)
    report = audit.audit_retained_option_exit_sources(settings, binding=binding)
    assert row(report, "ZERO")["reported_bid_size_covers_position"] is coverage
    assert report["reported_bid_size_unknown"] == unknown


def test_current_legacy_predicate_disagreement_is_exposed_without_promoting_exit(tmp_path):
    settings, binding, _, _ = fixture(tmp_path, bid_size=5, zero_volume=False)
    report = audit.audit_retained_option_exit_sources(settings, binding=binding)
    assert report["retained_classification_disagreements"] == 1
    assert row(report, "ZERO")["retained_rejection_reproduced"] is False
    assert report["historical_fill_authority"] is report["capital_released"] is False


@pytest.mark.parametrize("member", [0, 1, 2])
def test_missing_named_cache_member_is_explicit_and_other_positions_continue(tmp_path, member):
    settings, binding, review, _ = fixture(tmp_path)
    cache_paths(settings, review)[member].unlink()
    report = audit.audit_retained_option_exit_sources(settings, binding=binding)
    assert report["status"] == "COMPLETE_EXACT_EXIT_SOURCE_AUDIT_WITH_CACHE_GAPS"
    assert report["missing_position_sources"] == 1
    assert report["raw_option_files_read"] == 2
    assert row(report, "ZERO")["status"] == "CACHE_EVIDENCE_MISSING"
    assert row(report, "ZERO")["legacy_failure_reasons"] is None


def test_raw_body_drift_does_not_rebind_or_rebuild_cache(tmp_path):
    settings, binding, review, _ = fixture(tmp_path)
    path = cache_paths(settings, review)[0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="SHA drifted"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


@pytest.mark.parametrize("member,field", [(1, "receipt_fingerprint"), (2, "intent_fingerprint")])
def test_receipt_or_intent_tampering_blocks(tmp_path, member, field):
    settings, binding, review, _ = fixture(tmp_path)
    path = cache_paths(settings, review)[member]
    value = json.loads(path.read_text())
    value["extra"] = "changed"
    save(path, value)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match=field):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


@pytest.mark.parametrize("change,error", [
    ({"status": "QUARANTINED_REVIEW_REQUIRED"}, "classification or provenance"),
    ({"body_bytes": 1}, "classification or provenance"),
    ({"safe_summary": {}}, "classification or provenance"),
    ({"rate_limit": None}, "rate-limit metadata"),
])
def test_resigned_receipt_still_requires_original_body_classification(tmp_path, change, error):
    settings, binding, review, _ = fixture(tmp_path)
    path = cache_paths(settings, review)[1]
    value = json.loads(path.read_text())
    value.update(change)
    save(path, signed(value, "receipt_fingerprint"))
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match=error):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_exact_exit_projection_cannot_drift_from_pinned_physical_quote(tmp_path):
    settings, binding, review, scenario = fixture(tmp_path)
    scenario["cases"][0]["strategy_exit_option_mark"]["bid_per_share"] = "999"
    settings, binding, _, _ = rebind(settings, binding, review, scenario)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="bid projection drifted"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_recorded_failed_exit_clock_cannot_be_moved_past_early_close(tmp_path):
    settings, binding, review, scenario = fixture(tmp_path)
    next(item for item in review["unresolved_positions"] if item["ticker"] == "EARLY")["recorded_failed_exit_at_utc"] = "2021-11-26T21:00:00+00:00"
    settings, binding, _, _ = rebind(settings, binding, review, scenario)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="stock-session close"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_resigned_query_changes_cannot_reuse_an_original_request_identity(tmp_path):
    settings, binding, review, _ = fixture(tmp_path)
    paths = cache_paths(settings, review)
    for path, field in ((paths[1], "receipt_fingerprint"), (paths[2], "intent_fingerprint")):
        value = json.loads(path.read_text())
        value["query"]["from_inclusive"] = "2021-09-28"
        save(path, signed(value, field))
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="request/attempt identity"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_later_quote_cannot_replace_missing_exact_exit_session(tmp_path):
    settings, binding, _, _ = fixture(tmp_path, late_exact_absent=True)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="exact-exit quote missing"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_source_window_is_checked_before_opening_any_protected_body(tmp_path, monkeypatch):
    settings, binding, _, _ = fixture(tmp_path, query_end="2026-01-02")
    original = audit._read
    def guarded(path, **kwargs):
        assert "candidate_cache" not in str(path) or path.name.endswith(("receipt.json", "attempt.json"))
        return original(path, **kwargs)
    monkeypatch.setattr(audit, "_read", guarded)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="entry/exit/expiry scope"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


@pytest.mark.parametrize("target", ["review_path", "scenario_path"])
def test_original_report_byte_hashes_are_pinned_not_only_self_signatures(tmp_path, target):
    settings, binding, _, _ = fixture(tmp_path)
    path = settings.resolved_path(getattr(binding, target))
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="SHA drifted"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


@pytest.mark.parametrize("limit", ["MAX_RAW_BYTES", "MAX_RECEIPT_BYTES", "MAX_REVIEW_BYTES", "MAX_REPORT_BYTES"])
def test_every_input_group_has_a_bounded_read(tmp_path, monkeypatch, limit):
    settings, binding, _, _ = fixture(tmp_path)
    monkeypatch.setattr(audit, limit, 1)
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="oversized"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


def test_source_body_links_are_rejected_even_if_target_bytes_match(tmp_path):
    settings, binding, review, _ = fixture(tmp_path)
    path = cache_paths(settings, review)[0]
    target = tmp_path / "other.json"
    target.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("local symlink privilege unavailable")
    with pytest.raises(audit.RetainedOptionExitSourceAuditError, match="unsafe source cache"):
        audit.audit_retained_option_exit_sources(settings, binding=binding)


@pytest.mark.parametrize("raw", [b'{"s":"ok","s":"ok"}', b'{"s":NaN}', b'{"s":1e999}'])
def test_strict_json_rejects_duplicate_and_nonfinite_values(raw):
    with pytest.raises(audit.RetainedOptionExitSourceAuditError):
        audit._object(raw)


def test_cli_saves_only_new_diagnostic_and_reports_all_positions(tmp_path, monkeypatch, capsys):
    from scripts import audit_retained_option_exit_sources_v1 as cli
    settings, binding, _, _ = fixture(tmp_path)
    originals = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "DEFAULT_BINDING", binding)
    monkeypatch.setattr(cli, "audit_retained_option_exit_sources", lambda cfg, progress:
        audit.audit_retained_option_exit_sources(cfg, binding=binding, progress=progress))
    assert cli.main(["--save-report"]) == 0
    saved = list(settings.resolved_path(audit.OUTPUT_REL).glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text())["equity"] is None
    assert {path: path.read_bytes() for path in originals} == originals
    assert "exact source 3/3" in capsys.readouterr().out


def test_cli_integrity_failure_is_blocked_and_does_not_save_report(tmp_path, monkeypatch, capsys):
    from scripts import audit_retained_option_exit_sources_v1 as cli
    settings, binding, review, _ = fixture(tmp_path)
    cache_paths(settings, review)[0].write_bytes(b"changed")
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "audit_retained_option_exit_sources", lambda cfg, progress:
        audit.audit_retained_option_exit_sources(cfg, binding=binding, progress=progress))
    assert cli.main(["--save-report"]) == 3
    assert not settings.resolved_path(audit.OUTPUT_REL).exists()
    assert "BLOCKED" in capsys.readouterr().out
