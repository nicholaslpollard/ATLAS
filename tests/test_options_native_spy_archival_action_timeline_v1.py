from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data import options_native_spy_archival_action_timeline_v1 as mod
from scripts import index_options_native_spy_archival_actions_v1 as cli


def row(kind, page, index, symbol, **kwargs):
    return {
        "action_type": kind,
        "source_page_index": page,
        "source_record_index": index,
        "payload": {"symbol": symbol, **kwargs},
    }


def pages():
    return [{"sha256": "a" * 64}, {"sha256": "b" * 64}]


def test_ledger_candidate_selector_keeps_distinct_archival_types_and_unknown_dates():
    items = [
        row("cash_dividends", 0, 1, "SPY", ex_date="2019-12-20", rate=1.569992),
        row("cash_dividends", 0, 2, "SPY", ex_date="2020-03-20", rate=1.405559),
        row("cash_dividends", 0, 3, "SPY", ex_date="2015-01-02", rate=0.7),
        row("cash_dividends", 0, 4, "XYZ", ex_date="2019-12-20", rate=0.3),
        row("reorganizations", 1, 1, "SPY", effective_date="2022-02-01"),
        row("identity_changes", 1, 2, "SPY"),
        row("cash_dividends", 1, 3, "SPY", ex_date="2019-12-20", rate=1.569993),
    ]
    found = mod.projected_archival_events(items, pages())
    assert len(found) == 5
    assert [x["action_type"] for x in found] == [
        "cash_dividends", "cash_dividends", "reorganizations",
        "identity_changes", "cash_dividends",
    ]
    assert found[0]["manifest_recorded_source_page_sha256"] == "a" * 64
    assert found[3]["effective_date_state"] == "UNKNOWN_EFFECTIVE_DATE"
    assert all(x["point_in_time_qualified"] is False for x in found)
    assert found[0]["historical_available_at_utc"] is None
    assert found[-1]["payload"]["rate"] != found[0]["payload"]["rate"]


def test_case_projection_never_uses_first_baseline_date_or_future_dividend():
    items = [
        row("cash_dividends", 0, 1, "SPY", ex_date="2019-12-04", rate=1.1),
        row("cash_dividends", 0, 2, "SPY", ex_date="2019-12-20", rate=1.569992),
        row("cash_dividends", 0, 3, "SPY", ex_date="2020-03-20", rate=1.405559),
        row("identity_changes", 1, 4, "SPY"),
    ]
    events = mod.projected_archival_events(items, pages())
    case = {
        "decision_date": "2020-01-06", "quote_query_fingerprint": "a" * 64,
        "prior_close_keys": [
            "2019-12-04T20:59:00+00:00", "2019-12-20T20:59:00+00:00",
            "2020-01-03T20:59:00+00:00",
        ], "missing_clocks": [],
    }
    future = {
        "decision_date": "2020-03-23", "quote_query_fingerprint": "b" * 64,
        "prior_close_keys": [
            "2020-02-19T20:59:00+00:00", "2020-03-20T19:59:00+00:00",
        ], "missing_clocks": [mod.MISSING_CLOCK],
    }
    result = mod.index_weekly_action_exposure([case, future], events)
    assert result[0]["archived_dated_action_candidate_indices"] == [1]
    assert result[1]["archived_dated_action_candidate_indices"] == [2]
    assert result[0]["archived_undated_action_candidate_indices"] == [3]
    assert result[0]["physical_prior_and_spot_present"] is True
    assert result[1]["physical_prior_and_spot_present"] is False
    assert all(x["archival_zero_action_coverage_proved"] is False
               and x["historical_publication_revisions_proved"] is False
               and x["historical_economic_returns_accepted"] is False
               and x["forecast_total_variance"] is None for x in result)


@pytest.mark.parametrize("reason", ["duplicate", "wrong_page", "bad_ordinal", "malformed_date"])
def test_invalid_ledger_row_or_date_blocks(reason):
    item = row("cash_dividends", 0, 1, "SPY", ex_date="2020-01-01", rate=1.2)
    records = [item]
    if reason == "duplicate":
        records.append(item)
    if reason == "wrong_page":
        item["source_page_index"] = 2
    if reason == "bad_ordinal":
        item["source_record_index"] = True
    if reason == "malformed_date":
        item["payload"]["ex_date"] = "tomorrow"
    with pytest.raises((mod.SpyArchivalTimelineError, ValueError)):
        mod.projected_archival_events(records, pages())


def test_pinned_report_loader_rejects_sha_drift_and_report_resigning(tmp_path):
    report = {"contract": "synthetic", "economic_log_returns": None}
    report["report_fingerprint"] = _fingerprint(report)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    pin = mod.PinnedSource("report.json", hashlib.sha256(path.read_bytes()).hexdigest(),
                           report["report_fingerprint"])
    settings = SimpleNamespace(resolved_path=lambda rel: tmp_path / rel)
    assert mod._load_pinned(settings, pin) == report
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(mod.SpyArchivalTimelineError, match="raw-byte"):
        mod._load_pinned(settings, pin)
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    wrong = dict(report, historical_qualified=True)
    path.write_text(json.dumps(wrong, sort_keys=True) + "\n", encoding="utf-8")
    renamed = mod.PinnedSource(pin.path, hashlib.sha256(path.read_bytes()).hexdigest(),
                               report["report_fingerprint"])
    with pytest.raises(mod.SpyArchivalTimelineError, match="fingerprint"):
        mod._load_pinned(settings, renamed)


def test_fixed_coverage_proof_cannot_be_promoted_after_resigning():
    report = dict(contract="atlas-options-native-spy-development-minute-clock-coverage-v1",
                  status="PHYSICAL_COVERAGE_REVIEW_ONLY_NO_PIT_INPUT_ACCEPTANCE",
                  target_weekly_cases=411)
    with pytest.raises(mod.SpyArchivalTimelineError):
        mod.verify_source_bindings(report, {})


def test_script_cli_fails_closed_when_source_proof_missing(tmp_path, monkeypatch, capsys):
    settings = SimpleNamespace(
        resolved_path=lambda rel: tmp_path / rel,
        assert_external_storage_binding=lambda *_: None,
    )
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    assert cli.main(["--save-report"]) == 3
    assert "BLOCKED:" in capsys.readouterr().out
    assert not (tmp_path / "data/research/options_native_spy_archival_action_timeline_v1").exists()
