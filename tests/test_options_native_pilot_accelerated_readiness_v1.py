from __future__ import annotations

from pathlib import Path

import pytest

from packages.data import options_native_pilot_accelerated_readiness_v1 as v16
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import build_options_native_pilot_plan
from scripts import run_spy_pilot_integrated_acquisition_v1 as cli


class Settings:
    def assert_external_storage_binding(self, label):
        assert label == "options"


@pytest.fixture(scope="module")
def frozen():
    planned = build_options_native_pilot_plan()
    requests = planned["entry_quote_surface_requests"]
    assert len(requests) == 411
    rows = []
    for priority, original in enumerate(requests, 1):
        row = _entry(
            v16.SPY_ORIGIN, "a" * 64,
            original["query_fingerprint"],
            {"endpoint": original["endpoint"],
             "params": original["params"]},
            role="WEEKLY_ENTRY_DECISION", anchor=False,
        )
        row["priority"] = priority
        rows.append(row)
    return {
        "manifest_fingerprint": v16.PINNED_MANIFEST_FINGERPRINT,
        "source_request_count": 9866,
        "requests": rows,
    }


def test_all_411_original_frozen_spy_entry_clocks_and_2055_exit_uses(
    frozen, monkeypatch,
):
    monkeypatch.setattr(v16, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(v16, "_inspect_attempt", lambda *_: "UNATTEMPTED")
    report = v16.review_native_pilot_acquisition_readiness(
        Settings(), Path("frozen"), Path("source"),
        with_quote_geometry=False,
    )
    assert report["entry_required"] == 411
    assert report["entry_covered_v12_sources"] == 0
    assert report["entry_outstanding_unattempted"] == 410
    assert report["separately_saved_2025_spy_diagnostic"] == 1
    assert report["exit_review_uses"] == 411 * 5
    assert 1000 < report["distinct_exit_review_queries"] <= 2055
    assert report["exit_queries_reusing_frozen_entry_scope"] >= 1
    assert report["additional_distinct_exit_review_queries"] > 0
    assert all(x["simulator_ready"] is False for x in report["entry_source_states"]
               if "simulator_ready" in x)
    assert report["simulator_ready"] is False
    assert report["provider_requests"] == 0
    assert report["protected_outcomes_read"] == 0
    assert report["files_written"] == 0
    assert "PRIOR_STATE_OPTION_OPEN_INTEREST_NOT_BOUND" in report[
        "remaining_simulator_blockers"
    ]


def test_first_frozen_entry_clock_is_truly_first_session(
    frozen,
):
    first = frozen["requests"][0]
    assert first["date_et"] == "2018-01-02"
    from datetime import date
    sessions = v16._exit_review_sessions(date.fromisoformat(first["date_et"]))
    assert len(sessions) == 5
    assert sessions[0].isoformat() == "2018-01-03"
    assert all(a < b for a, b in zip(sessions, sessions[1:]))


def test_selected_quotes_use_native_30_45_dte_30s_not_broad_14_45(
    frozen, monkeypatch,
):
    first_qid = frozen["requests"][0]["query_id"]
    monkeypatch.setattr(v16, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(
        v16, "_inspect_attempt",
        lambda _settings, qid:
            "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC" if qid == first_qid
            else "UNATTEMPTED",
    )
    monkeypatch.setattr(
        v16, "read_selected_original_observations",
        lambda _settings, row: {"query_id": row["query_id"]},
    )
    captured = []
    def summarize(selection, **kwargs):
        captured.append(kwargs)
        assert selection["query_id"] == first_qid
        return {
            "research_window_observed_rows": 24,
            "observed_call_put_strike_pairs": 12,
            "observed_pairs_passing_freshness_spread_only": 11,
            "research_window_stale_rows": 1,
            "research_window_wide_spread_rows": 0,
        }
    monkeypatch.setattr(v16, "summarize_selected_chain", summarize)
    report = v16.review_native_pilot_acquisition_readiness(
        Settings(), Path("frozen"), Path("source"),
        with_quote_geometry=True,
    )
    assert captured == [{
        "dte_min": 30, "dte_max": 45,
        "max_quote_age_seconds": 30, "max_spread_to_mid": 0.15,
    }]
    assert report["pilot_quote_diagnostics"]["observed_pairs"] == 12
    assert report["pilot_quote_diagnostics"]["fresh_spread_pairs_only"] == 11
    assert report["pilot_quote_diagnostics"]["indexed_entry_clocks"] == 1
    assert report["simulator_ready"] is False


def test_invalid_spy_archive_not_silently_marked_ready(frozen, monkeypatch):
    monkeypatch.setattr(v16, "_load_full_manifest", lambda *_: frozen)
    first_qid = frozen["requests"][0]["query_id"]
    monkeypatch.setattr(
        v16, "_inspect_attempt",
        lambda _settings, qid:
            "RAW_ARCHIVED_INVALID_SCHEMA" if qid == first_qid
            else "UNATTEMPTED",
    )
    with pytest.raises(v16.NativePilotAcceleratedReadinessError):
        v16.review_native_pilot_acquisition_readiness(
            Settings(), Path("frozen"), Path("source"),
            with_quote_geometry=False,
        )


def test_request_query_fingerprint_is_exact_reconstructable_not_authority():
    from datetime import date
    item = v16._exit_at_time_query(date(2018, 1, 3))
    assert item["query_id"] == _fingerprint({
        "provider": "thetadata",
        "endpoint": item["endpoint"], "params": item["params"],
    })
    assert item["params"]["right"] == "both"
    assert item["params"]["max_dte"] == 45
    assert item["source_complete"] is False
    assert item["simulator_ready"] is False


def test_integrated_cli_scopes_to_spy_and_indexes_only_on_run(
    frozen, monkeypatch, capsys,
):
    settings = Settings()
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    calls = []
    def readiness(_settings, _manifest, _candidate, *, with_quote_geometry):
        calls.append(("ready", with_quote_geometry))
        return {
            "entry_required": 411, "entry_covered_v12_sources": 10,
            "separately_saved_2025_spy_diagnostic": 1,
            "entry_outstanding_unattempted": 400,
            "exit_review_uses": 2055,
            "additional_distinct_exit_review_queries": 1644,
            "pilot_quote_diagnostics": {
                "research_window_rows": 15,
                "observed_pairs": 6,
            },
            "entry_states": {"UNATTEMPTED": 400},
            "remaining_simulator_blockers": list(v16.BLOCKERS),
            "fingerprint": "f" * 64,
        }
    def acquire(_settings, _manifest, _candidate, **kwargs):
        calls.append(("download", kwargs["allowed_origin"],
                      kwargs["max_calls"], kwargs["progress_every"]))
        kwargs["progress"]({
            "completed_calls": 25, "archived": 25,
            "out_of_dte": 25, "last_date": "2018-12-31",
            "last_request_id": "a" * 64,
            "state": "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
        })
        return {
            "provider_calls_this_run": 400,
            "archives_written_this_run": 400,
            "out_of_dte_archives_this_run": 400,
            "invalid_schema_archives_this_run": 0,
            "stop_reason": "FULL_FROZEN_MANIFEST_SCANNED",
        }
    def build(_settings, _manifest, _candidate, **kwargs):
        calls.append(("indexes", kwargs["write_indexes"]))
        return {
            "original_archives_scanned": 410,
            "in_requested_dte_references": 5000,
            "new_immutable_indices": 400,
        }
    monkeypatch.setattr(cli, "review_native_pilot_acquisition_readiness",
                        readiness)
    monkeypatch.setattr(cli, "run_campaign", acquire)
    monkeypatch.setattr(cli, "build_dte_reference_indices", build)
    assert cli.main([]) == 0
    assert calls == [("ready", False), ("ready", True)]
    calls.clear()
    assert cli.main(["--run", "--progress-every", "25"]) == 0
    assert calls == [
        ("ready", False),
        ("download", v16.SPY_ORIGIN, None, 25),
        ("indexes", True),
        ("ready", True),
    ]
    out = capsys.readouterr().out
    assert "typed_authorizations=0" in out
    assert "PROGRESS: calls=25" in out
    assert "simulator_ready=False" in out
    assert "protected_outcomes_read=0" in out
