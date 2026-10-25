from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import (
    hybrid_options_acquisition_reservations_v1 as v7,
    thetadata_hourly_source_canary_v1 as canary,
)
from packages.data.hybrid_options_archive_reader_v1 import (
    load_verified_archived_option_quotes,
)
from packages.data.hybrid_options_coverage_catalog_v1 import ingest_hourly_source
from packages.data.hybrid_options_gap_planner_v1 import demo_batch
from packages.data.hybrid_options_lossless_archive_v1 import archive_existing_source
from packages.data.hybrid_options_source_store_v2 import (
    store_historical_quote_source,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import plan_hybrid_options_offline_acquisition_v1 as cli


class FakeSettings:
    def __init__(self, root: Path):
        self.root = root
        (root / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, binding):
        assert binding == "options"

    def resolved_path(self, relative):
        return self.root / relative


def snapshot(*, free=180.0, remaining=180.0,
             candidate=1.0, candidate_quota=120.0,
             warning=40.0, status="SAFE"):
    return SimpleNamespace(
        storage_mode="EXTERNAL_SECONDARY",
        disk_free_gib=free, warning_free_gib=warning,
        remaining_acquisition_budget_gib=remaining,
        category_usage_gib={"options_candidate_cache": candidate},
        category_quota_gib={"options_candidate_cache": candidate_quota},
        acquisition_budget_gib=190.0,
        status=status,
    )


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda path: SimpleNamespace(free=200 * 1024**3),
    )
    settings = FakeSettings(tmp_path)
    return settings, (lambda _: snapshot())


def q():
    return demo_batch()["requests"][0]["query"]


def sample_rows(*, bid=3.0):
    when = datetime(
        2025, 6, 9, 10, 30, tzinfo=ZoneInfo("America/New_York")
    ).isoformat()
    return tuple({
        "symbol": "SPY", "expiration": "2025-07-18",
        "strike": 500.0, "right": right, "timestamp": when,
        "bid": bid, "ask": 3.5, "bid_size": 5, "ask_size": 6,
    } for right in ("CALL", "PUT"))


def sdk_response(*, bid=3.0):
    rows = sample_rows(bid=bid)
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={},
        raw_body=raw, response_bytes=len(raw), elapsed_seconds=0.01,
        transport=TRANSPORT, library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="a" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


def put_v6(settings, *, bid=3.0):
    return store_historical_quote_source(
        settings, q(), response=sdk_response(bid=bid), write=True,
    )


def put_v4(settings):
    def fake_reader(**kwargs):
        assert kwargs["symbol"] == "SPY"
        return sdk_response()
    report = canary.run_one_hourly_source_canary(
        settings, reader=fake_reader, authorize_one_hourly_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    old = ingest_hourly_source(settings, Path(report["report_path"]))
    assert archive_existing_source(
        settings, old["source_id"], write_archive=True
    )["archive_present"]
    return old


def state(report, symbol, date, interval):
    return next(x for x in report["queries"]
                if x["query"]["symbol"] == symbol
                and x["query"]["date_et"] == date
                and x["query"]["interval"] == interval)


def test_reconcile_v6_source_without_reacquisition(setup):
    settings, reader = setup
    put_v6(settings)
    report = v7.plan_acquisition_reservations(
        settings, demo_batch(), storage_reader=reader,
    )
    assert report["requirement_uses"] == 5
    assert report["unique_queries"] == 4
    assert report["deduplicated_uses"] == 1
    assert report["verified_local_queries"] == 1
    assert report["missing_exact_queries"] == 3
    assert report["newly_reservable_queries"] == 2
    assert report["blocked_adapter_queries"] == 1
    assert report["provider_requests"] == 0
    assert report["paid_provider_authority"] is False
    assert report["simulator_ready"] is False
    observed = state(report, "SPY", "2025-06-09", "1h")
    assert observed["status"] == "REUSE_VERIFIED_UNQUALIFIED_SOURCE"
    assert len(observed["verified_sources"]) == 1
    assert len(observed["uses"]) == 2
    assert state(report, "SPY", "2025-06-09", "1m")[
        "status"
    ] == "BLOCKED_EXACT_ADAPTER_UNAVAILABLE"
    assert state(report, "QQQ", "2025-06-09", "1h")[
        "status"
    ] == "ELIGIBLE_FOR_OFFLINE_RESERVATION_ONLY"
    assert state(report, "SPY", "2018-06-11", "1h")[
        "status"
    ] == "ELIGIBLE_FOR_OFFLINE_RESERVATION_ONLY"
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()


def test_reconcile_v4_and_v6_mirrored_source(setup):
    settings, reader = setup
    legacy = put_v4(settings)
    known = load_verified_archived_option_quotes(
        settings, legacy["source_id"],
    )
    store_historical_quote_source(
        settings, known["query_scope"], verified_v4=known, write=True,
    )
    result = v7.plan_acquisition_reservations(
        settings, demo_batch(), storage_reader=reader,
    )
    observed = state(result, "SPY", "2025-06-09", "1h")
    assert {s["store"] for s in observed["verified_sources"]} == {"V4", "V6"}
    assert result["verified_local_queries"] == 1
    assert result["missing_exact_queries"] == 3


def test_conflicting_v4_and_v6_bodies_fail_closed(setup):
    settings, reader = setup
    put_v4(settings)
    put_v6(settings, bid=2.0)
    with pytest.raises(
        v7.HybridAcquisitionPlanError, match="CONFLICTING_SOURCE_BODIES",
    ):
        v7.plan_acquisition_reservations(
            settings, demo_batch(), storage_reader=reader, reserve=True,
        )
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()


def test_reservation_is_explicit_idempotent_no_provider_attempt(setup):
    settings, reader = setup
    put_v6(settings)
    first = v7.plan_acquisition_reservations(
        settings, demo_batch(), reserve=True, storage_reader=reader,
    )
    assert first["new_reservations"] == 2
    assert first["newly_planned_reservation_bytes"] == 256 * v7.MIB
    assert first["provider_requests"] == 0
    assert first["reservation_is_not_an_api_attempt"] is True
    old = state(first, "SPY", "2018-06-11", "1h")
    assert old["status"] == "RESERVED_NO_PROVIDER_CALL"
    proof = v7._reservation_path(settings, old["query_id"])
    body = json.loads(proof.read_text())
    assert body["provider_attempts"] == 0
    assert body["provider_authorized"] is False
    assert body["automatic_retries_allowed"] is False
    again = v7.plan_acquisition_reservations(
        settings, demo_batch(), reserve=True, storage_reader=reader,
    )
    assert again["new_reservations"] == 0
    assert again["already_reserved_queries"] == 2
    assert body == json.loads(proof.read_text())


def test_corrupted_reservation_never_releases_provider_retry(setup):
    settings, reader = setup
    put_v6(settings)
    report = v7.plan_acquisition_reservations(
        settings, demo_batch(), reserve=True, storage_reader=reader,
    )
    query = state(report, "QQQ", "2025-06-09", "1h")
    receipt = v7._reservation_path(settings, query["query_id"])
    modified = json.loads(receipt.read_text())
    modified["provider_authorized"] = True
    receipt.write_text(json.dumps(modified))
    with pytest.raises(
        v7.HybridAcquisitionPlanError, match="RECEIPT_OR_AUTHORITY_DRIFT",
    ):
        v7.plan_acquisition_reservations(
            settings, demo_batch(), reserve=True, storage_reader=reader,
        )


@pytest.mark.parametrize("budget", [0, -1, 8193, True])
def test_invalid_budget_rejected_without_files(setup, budget):
    settings, reader = setup
    with pytest.raises(
        v7.HybridAcquisitionPlanError, match="UNBOUNDED",
    ):
        v7.plan_acquisition_reservations(
            settings, demo_batch(), batch_budget_mib=budget,
            reserve=True, storage_reader=reader,
        )
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()


def test_tight_budget_defers_deterministically(setup):
    settings, reader = setup
    put_v6(settings)
    result = v7.plan_acquisition_reservations(
        settings, demo_batch(), batch_budget_mib=128,
        per_request_mib=128, storage_reader=reader,
    )
    assert result["newly_reservable_queries"] == 1
    assert result["deferred_budget_queries"] == 1
    assert state(result, "SPY", "2018-06-11", "1h")[
        "status"
    ] == "ELIGIBLE_FOR_OFFLINE_RESERVATION_ONLY"
    assert state(result, "QQQ", "2025-06-09", "1h")[
        "status"
    ] == "DEFERRED_REQUEST_OR_STORAGE_BUDGET"


def test_aggregate_shared_quota_checks_hybrid_and_candidate_cache(setup):
    settings, _ = setup
    put_v6(settings)
    reader = lambda _: snapshot(candidate=119.99, candidate_quota=120)
    result = v7.plan_acquisition_reservations(
        settings, demo_batch(), storage_reader=reader,
    )
    assert result["newly_reservable_queries"] == 0
    assert result["deferred_budget_queries"] == 2
    assert result["provider_requests"] == 0


def test_low_disk_headroom_blocks_all_new_reservations(setup):
    settings, _ = setup
    put_v6(settings)
    reader = lambda _: snapshot(free=39.8, remaining=170)
    result = v7.plan_acquisition_reservations(
        settings, demo_batch(), reserve=True, storage_reader=reader,
    )
    assert result["new_reservations"] == 0
    assert result["deferred_budget_queries"] == 2
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()


def test_unusable_verified_archive_is_integrity_failure_not_new_work(setup):
    settings, reader = setup
    stored = put_v6(settings)
    archive, _ = __import__(
        "packages.data.hybrid_options_source_store_v2",
        fromlist=["_paths"],
    )._paths(settings, stored["source_id"])
    archive.unlink()
    with pytest.raises(ValueError):
        v7.plan_acquisition_reservations(
            settings, demo_batch(), storage_reader=reader, reserve=True,
        )
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()


def test_missing_all_sources_does_not_make_minute_adapter_ready(setup):
    settings, reader = setup
    result = v7.plan_acquisition_reservations(
        settings, demo_batch(), storage_reader=reader,
    )
    assert result["verified_local_queries"] == 0
    assert result["newly_reservable_queries"] == 3
    assert result["blocked_adapter_queries"] == 1


def test_cli_read_only_and_explicit_reserve(setup, monkeypatch, capsys):
    settings, reader = setup
    put_v6(settings)
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    normal = v7.plan_acquisition_reservations
    monkeypatch.setattr(
        cli, "plan_acquisition_reservations",
        lambda settings, batch, **kwargs: normal(
            settings, batch, storage_reader=reader, **kwargs,
        ),
    )
    assert cli.main(["--demo"]) == 0
    assert "newly_reserved=0" in capsys.readouterr().out
    assert not settings.resolved_path(v7.RESERVATION_ROOT).exists()
    assert cli.main(["--demo", "--reserve"]) == 0
    output = capsys.readouterr().out
    assert "newly_reserved=2" in output
    assert "paid_authority=False" in output
    assert cli.main(["--demo", "--reserve"]) == 0
    assert "newly_reserved=0" in capsys.readouterr().out



def one_requirement(entry):
    from packages.data.hybrid_options_gap_planner_v1 import BATCH_CONTRACT
    return {"contract": BATCH_CONTRACT, "requests": [entry]}


def test_cross_batch_outstanding_reservations_reduce_budget(setup):
    settings, _ = setup
    limited = lambda _: snapshot(remaining=0.2)
    entries = demo_batch()["requests"]
    old = one_requirement(entries[4])
    new = one_requirement(entries[3])
    first = v7.plan_acquisition_reservations(
        settings, old, reserve=True, storage_reader=limited,
    )
    assert first["new_reservations"] == 1
    second = v7.plan_acquisition_reservations(
        settings, new, reserve=True, storage_reader=limited,
    )
    assert second["outstanding_no_call_reservations_before_batch"] == 1
    assert second["outstanding_reservation_bytes_before_batch"] == 128 * v7.MIB
    assert second["new_reservations"] == 0
    assert second["deferred_budget_queries"] == 1


def test_unrelated_reservation_tampering_blocks_later_batch(setup):
    settings, reader = setup
    entries = demo_batch()["requests"]
    old = one_requirement(entries[4])
    newer = one_requirement(entries[3])
    reserved = v7.plan_acquisition_reservations(
        settings, old, reserve=True, storage_reader=reader,
    )
    id_ = reserved["queries"][0]["query_id"]
    path = v7._reservation_path(settings, id_)
    body = json.loads(path.read_text())
    body["provider_attempts"] = 1
    path.write_text(json.dumps(body))
    with pytest.raises(v7.HybridAcquisitionPlanError):
        v7.plan_acquisition_reservations(
            settings, newer, reserve=True, storage_reader=reader,
        )
    assert len(list(settings.resolved_path(v7.RESERVATION_ROOT).rglob("*.json"))) == 1
