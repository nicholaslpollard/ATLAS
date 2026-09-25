from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data import marketdata_accepted_stock_candidate_export_v1 as exporter
from packages.data.marketdata_candidate_chain_cache_v1 import verify_candidate_plan


ROOT = Path(__file__).resolve().parents[1]


def _case(number, signal_session, *, timeframe="1d", direction="LONG", price=100.0):
    calendar = get_market_calendar()
    entry = next(
        day for day in calendar.sessions_in_range(
            signal_session + timedelta(days=1),
            signal_session + timedelta(days=7),
        )
    )
    entry_utc, _ = calendar.regular_open_close(entry)
    return SimpleNamespace(
        opportunity_id=f"accepted-case-{number}",
        signal_session=signal_session,
        native_timeframe=timeframe,
        direction=direction,
        ticker="SPY",
        instrument_id=f"instrument-{number}",
        policy_id="accepted-policy",
        entry_utc=entry_utc,
        synthetic_future_outcome=price,  # intentionally never read by selector
    )


def test_monthly_cohort_is_deterministic_independent_of_row_order_and_outcomes():
    rows = [
        _case(1, date(2025, 9, 15)),
        _case(2, date(2025, 9, 16)),
        _case(3, date(2025, 10, 13)),
        _case(4, date(2025, 10, 14), direction="SHORT"),
        _case(5, date(2025, 10, 15), timeframe="1min"),
        _case(6, date(2025, 10, 16)),
    ]
    rows[-1].ticker = "BAD/TICKER"
    one = exporter.select_monthly_cohort(rows, year=2025, per_month=1)
    two = exporter.select_monthly_cohort(list(reversed(rows)), year=2025, per_month=1)
    assert [x.opportunity_id for x in one] == [x.opportunity_id for x in two]
    assert len(one) == 2
    assert all(x.direction == "LONG" and x.native_timeframe == "1d" for x in one)
    rows[0].synthetic_future_outcome = -100000
    assert [x.opportunity_id for x in one] == [
        x.opportunity_id for x in exporter.select_monthly_cohort(rows, year=2025, per_month=1)
    ]


def test_expiration_is_exchange_session_and_bounded():
    for session in (date(2025, 3, 20), date(2025, 9, 15), date(2026, 4, 1)):
        expiry = exporter._monthly_expiration(session)
        assert get_market_calendar().is_session(expiry)
        assert 28 <= (expiry - session).days <= 60


def test_stock_bundle_physically_matches_plan_source_sha_and_is_reusable(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": project})
    rows = [
        _case(1, date(2025, 9, 15)),
        _case(2, date(2025, 9, 16)),
        _case(3, date(2025, 10, 13)),
    ]
    monkeypatch.setattr(
        exporter, "load_selected_replay_opportunities",
        lambda *_args, **_kwargs: (
            tuple(rows),
            {
                "source_integrity_fingerprint": "b" * 64,
                "conditioning_analysis_fingerprint": "c" * 64,
            },
        ),
    )
    monkeypatch.setattr(
        exporter, "_read_entry_opens",
        lambda _project, _cohort, **_kwargs: (
            {row.opportunity_id: 100.0 for row in _cohort},
            {
                "source_fingerprint": "d" * 64,
                "manifest_sha256": "e" * 64,
                "protected_master_return_rows_read": 0,
                "native_raw_source": {
                    "native_acceptance_fingerprint": "f" * 64,
                    "verified_native_raw_unit_count": 1,
                    "verified_native_raw_unit_bindings": [{"unit_id": "fixture", "year": 2025, "canonical_sha256": "a" * 64}],
                },
            },
        ),
    )
    one = exporter.export_candidate_stock_manifest(settings, year=2025, per_month=1)
    two = exporter.export_candidate_stock_manifest(settings, year=2025, per_month=1)
    # The source bundle and chain plan are immutable across reruns, while each
    # invocation gets its own independently traceable run ID and stage report.
    for key in (
        "cohort_identity", "stock_source_sha256", "plan_fingerprint",
        "stock_source_file", "opportunities_file", "plan_file",
        "selected_opportunities", "shared_chain_requests",
    ):
        assert one[key] == two[key]
    assert one["source_only_run_id"] != two["source_only_run_id"]
    assert one["run_report_path"] != two["run_report_path"]
    for item in (one, two):
        report = json.loads(Path(item["run_report_path"]).read_text(encoding="utf-8"))
        assert report["status"] == "SOURCE_ONLY_COMPLETE"
        assert report["summary"]["source_sha256"] == one["stock_source_sha256"]
        assert report["summary"]["plan_fingerprint"] == one["plan_fingerprint"]
        assert report["stage"] == "COMPLETE"
        assert [stage["stage"] for stage in report["stages"]] == [
            "STARTED", "ACCEPTED_SOURCE_LOADING", "ACCEPTED_SOURCE_LOADED",
            "COHORT_SELECTED", "NATIVE_RAW_SOURCE_VERIFYING",
            "NATIVE_RAW_SOURCE_VERIFIED", "CHAIN_PLAN_READY",
            "ARTIFACTS_WRITTEN", "COMPLETE",
        ]
        assert report["provider_reads"] == 0
        assert report["report_fingerprint"] == exporter._hash({
            k: v for k, v in report.items() if k != "report_fingerprint"
        })
        assert item["elapsed_seconds"] >= 0
    assert one["selected_opportunities"] == 2
    assert one["verified_native_raw_units"] == 1
    source = Path(one["stock_source_file"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == one["stock_source_sha256"]
    plan = json.loads(Path(one["plan_file"]).read_text())
    assert verify_candidate_plan(plan) == plan
    assert {v["stock_source_sha256"] for v in plan["source_bindings"].values()} == {
        one["stock_source_sha256"]
    }
    assert all(
        datetime.fromisoformat(item["decision_at_utc"]).date()
        > date.fromisoformat(item["snapshot_date"])
        for item in plan["source_bindings"].values()
    )
    assert one["provider_reads"] == 0


def test_rejected_cohort_controls():
    with pytest.raises(exporter.CandidateStockExportError, match="per_month"):
        exporter.select_monthly_cohort([], year=2025, per_month=10)
    with pytest.raises(exporter.CandidateStockExportError, match="year"):
        exporter.select_monthly_cohort([], year=2020, per_month=1)


def test_export_failure_retains_last_stage_and_error_type_without_source_data(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": project})

    def fail_loader(*_args, **_kwargs):
        raise RuntimeError("fixture source unavailable")

    monkeypatch.setattr(exporter, "load_selected_replay_opportunities", fail_loader)
    with pytest.raises(RuntimeError, match="fixture source unavailable"):
        exporter.export_candidate_stock_manifest(settings, year=2025, per_month=1)
    reports = list(
        settings.resolved_path(
            "data/options/manifests/marketdata_stock_candidate_export_v1/runs"
        ).glob("*.json")
    )
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["status"] == "FAILED_REVIEW_REQUIRED"
    assert report["exception_type"] == "RuntimeError"
    assert report["stage"] == "FAILED_REVIEW_REQUIRED"
    assert report["provider_reads"] == 0
    assert report["stages"][-2]["stage"] == "ACCEPTED_SOURCE_LOADING"
    assert "fixture source unavailable" not in reports[0].read_text(encoding="utf-8")
