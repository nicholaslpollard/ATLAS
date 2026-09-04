from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from urllib.request import urlopen

import pytest

from packages.control_plane.paper_dashboard import PaperDashboardService
from packages.control_plane.phase19_http_server import create_phase19_status_server
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPreflightResult,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.execution_attempt import ExecutionAttemptRecord, ExecutionRiskRevalidation


NOW = datetime(2026, 9, 3, 21, 0, 0, tzinfo=UTC)


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path, "live": tmp_path / "live"})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attempt(direction: DiscoveryDirection) -> ExecutionAttemptRecord:
    bullish = direction == DiscoveryDirection.BULLISH
    stop = 95.0 if bullish else 105.0
    target = 110.0 if bullish else 90.0
    side = BrokerOrderSide.BUY if bullish else BrokerOrderSide.SHORT
    intent = ExecutionIntent(
        intent_id=f"intent-{direction.value}-1234567890",
        instrument_id=f"figi-{direction.value}",
        ticker="XYZ",
        as_of_date=NOW.date(),
        direction=direction,
        environment=ExecutionEnvironment.PAPER,
        broker=BrokerName.ALPACA,
        phase13_case_sha256="a" * 64,
        phase14_acceptance_sha256="b" * 64,
        reference_entry=100.0,
        entry_limit=100.0,
        stop=stop,
        target=target,
        original_risk_per_share=5.0,
        executable_risk_per_share=5.0,
        executable_reward_per_share=10.0,
        adverse_entry_drift_r=0.0,
        executable_reward_to_risk=2.0,
        accepted_risk_budget=500.0,
        accepted_proposed_quantity=10,
        executable_quantity=10,
        quote_bid=99.95,
        quote_ask=100.0,
        quote_provider_timestamp_utc=NOW - timedelta(seconds=1),
        quote_received_at_utc=NOW - timedelta(milliseconds=900),
        quote_feed_mode="realtime",
        quote_expected_delay_seconds=0,
        quote_age_seconds=1.0,
        session_segment="regular",
        order_type="LIMIT",
        time_in_force="DAY",
        reason_codes=("TEST_EXECUTION_INTENT",),
    )
    plan = BrokerOrderPlan(
        intent_id=intent.intent_id,
        client_order_id=f"atlas-{direction.value}-123456",
        ticker="XYZ",
        instrument_type="EQUITY",
        side=side,
        quantity=10,
        order_type="LIMIT",
        limit_price=100.0,
        stop_price=stop,
        target_price=target,
        time_in_force="DAY",
    )
    account = BrokerAccountSnapshot(
        broker=BrokerName.ALPACA,
        environment=ExecutionEnvironment.PAPER,
        account_id="paper-account",
        as_of_utc=NOW,
        equity=100_000.0,
        cash=99_000.0,
        buying_power=99_000.0,
        gross_market_value=0.0,
        trading_blocked=False,
        shorting_enabled=True,
    )
    reconciliation = BrokerReconciliationSnapshot(
        broker=BrokerName.ALPACA,
        environment=ExecutionEnvironment.PAPER,
        account=account,
        open_orders=(),
        positions=(),
        as_of_utc=NOW,
        reconciled=True,
        zero_open_orders=True,
        zero_positions=True,
        safe_to_switch_broker=True,
        reason_codes=("TEST_RECONCILED",),
    )
    risk = ExecutionRiskRevalidation(
        checked_at_utc=NOW,
        account_equity=100_000.0,
        account_gross_market_value=0.0,
        open_positions_before=0,
        existing_same_name_market_value=0.0,
        proposed_loss_at_stop=50.0,
        proposed_notional=1_000.0,
        projected_loss_fraction=0.0005,
        projected_single_name_fraction=0.01,
        projected_gross_fraction=0.01,
        projected_position_count=1,
        max_abs_correlation=None,
        admissible=True,
        reason_codes=("TEST_RISK_ADMISSIBLE",),
    )
    preflight = BrokerPreflightResult(
        broker=BrokerName.ALPACA,
        intent_id=intent.intent_id,
        accepted=True,
        as_of_utc=NOW,
        estimated_cost=1_000.0,
        estimated_fees=0.0,
        provider_code="TEST_ACCEPTED",
        reason_codes=("TEST_PREFLIGHT_ACCEPTED",),
    )
    order = BrokerOrderSnapshot(
        broker=BrokerName.ALPACA,
        account_id="paper-account",
        client_order_id=plan.client_order_id,
        provider_order_id="provider-test-order",
        ticker="XYZ",
        side=side,
        status=BrokerOrderStatus.FILLED,
        requested_quantity=10.0,
        filled_quantity=10.0,
        average_fill_price=100.0,
        submitted_at_utc=NOW,
        updated_at_utc=NOW,
        raw_status="FILLED",
    )
    return ExecutionAttemptRecord(
        attempted_at_utc=NOW,
        intent=intent,
        order_plan=plan,
        reconciliation_before=reconciliation,
        risk_revalidation=risk,
        preflight=preflight,
        order_snapshot=order,
        existing_order_reused=False,
        provider_submission_performed=True,
        broker_write_count=1,
        order_write_count=1,
        live_submission_performed=False,
    )


def _write_attempt_manifest(settings, attempt: ExecutionAttemptRecord, *, bad_hash: bool = False) -> None:
    root = settings.resolved_path(settings.data.paths.derived) / "execution" / "phase15" / "v1"
    attempt_path = root / "attempts" / attempt.intent.intent_id / "attempt.json"
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(attempt.model_dump_json(indent=2), encoding="utf-8")
    _write_json(
        root / "manifests" / "2026" / "2026-09-03.json",
        {
            "as_of_date": "2026-09-03",
            "generated_at_utc": NOW.isoformat(),
            "selected_environment": "paper",
            "selected_broker": "alpaca",
            "record_count": 1,
            "blocked_count": 0,
            "paper_submitted_count": 1,
            "existing_reconciled_count": 0,
            "provider_uncertain_count": 0,
            "requires_reconciliation": False,
            "pass": True,
            "records": [
                {
                    "ticker": "XYZ",
                    "as_of_date": "2026-09-03",
                    "environment": "paper",
                    "broker": "alpaca",
                    "disposition": "PAPER_SUBMITTED",
                    "reason_codes": ["TEST_PAPER_SUBMITTED"],
                    "provider_submission_attempted": True,
                    "provider_submission_uncertain": False,
                    "attempt_path": str(attempt_path.resolve()),
                    "attempt_sha256": "0" * 64 if bad_hash else _sha256(attempt_path),
                }
            ],
        },
    )


def _write_live_state(settings, *, bid: float, ask: float, provider_timestamp: datetime) -> None:
    _write_json(
        MarketDataPaths(settings).live_state_file(),
        {
            "generated_at_utc": NOW.isoformat(),
            "feed_mode": "realtime",
            "expected_delay_seconds": 0,
            "connection_state": "subscribed",
            "subscriptions": ["Q.XYZ"],
            "session": {
                "as_of_utc": NOW.isoformat(),
                "local_date": "2026-09-03",
                "is_exchange_session": True,
                "session_segment": "regular",
                "regular_open_utc": "2026-09-03T13:30:00+00:00",
                "regular_close_utc": "2026-09-03T20:00:00+00:00",
                "next_session_date": "2026-09-04",
                "next_regular_open_utc": "2026-09-04T13:30:00+00:00",
            },
            "received_events": 1,
            "accepted_events": 1,
            "ignored_out_of_order_events": 0,
            "parse_errors": 0,
            "reconnects": 0,
            "restored_symbol_count": 0,
            "observed_symbol_count": 1,
            "last_received_at_utc": NOW.isoformat(),
            "transport_gaps": [],
            "open_transport_gap_started_at_utc": None,
            "symbols": [
                {
                    "symbol": "XYZ",
                    "as_of_utc": NOW.isoformat(),
                    "minute": None,
                    "minute_freshness": "unknown",
                    "quote_freshness": "fresh",
                    "quote": {
                        "symbol": "XYZ",
                        "provider_timestamp_utc": provider_timestamp.isoformat(),
                        "session_date": "2026-09-03",
                        "session_segment": "regular",
                        "bid_price": bid,
                        "bid_size": 10,
                        "ask_price": ask,
                        "ask_size": 10,
                        "sequence": 1,
                        "provider": "massive",
                        "feed_mode": "realtime",
                        "expected_delay_seconds": 0,
                        "received_at_utc": provider_timestamp.isoformat(),
                    },
                }
            ],
        },
    )


def test_paper_dashboard_not_run_is_explicit_and_read_only(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    payload = PaperDashboardService(settings, now_utc=lambda: NOW).snapshot()
    assert payload["status"] == "NOT_RUN"
    assert payload["read_only"] is True
    assert payload["provider_reads"] == 0
    assert payload["provider_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["health"]["reason"] == "PHASE15_EXECUTION_MANIFEST_UNAVAILABLE"


def test_paper_dashboard_hash_mismatch_fails_closed(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    _write_attempt_manifest(settings, _attempt(DiscoveryDirection.BULLISH), bad_hash=True)
    payload = PaperDashboardService(settings, now_utc=lambda: NOW).snapshot()
    assert payload["status"] == "INVALID"
    assert payload["open_positions"] == []
    assert payload["broker_writes"] == 0
    assert payload["health"]["reason"] == "LOCAL_EXECUTION_EVIDENCE_FAILED_VALIDATION"


@pytest.mark.parametrize(
    ("direction", "bid", "ask", "expected_pnl"),
    [
        (DiscoveryDirection.BULLISH, 102.0, 102.1, 20.0),
        (DiscoveryDirection.BEARISH, 97.9, 98.0, 20.0),
    ],
)
def test_paper_dashboard_marks_long_at_bid_and_short_at_ask(
    tmp_path, direction, bid, ask, expected_pnl
) -> None:
    settings = _settings_with_derived(tmp_path)
    _write_attempt_manifest(settings, _attempt(direction))
    _write_live_state(settings, bid=bid, ask=ask, provider_timestamp=NOW - timedelta(seconds=5))
    payload = PaperDashboardService(settings, now_utc=lambda: NOW).snapshot()
    assert payload["status"] == "AVAILABLE"
    assert len(payload["open_positions"]) == 1
    position = payload["open_positions"][0]
    assert position["current_mark"] == pytest.approx(bid if direction == DiscoveryDirection.BULLISH else ask)
    assert position["unrealized_pnl"] == pytest.approx(expected_pnl)
    assert position["mark_state"] == "FRESH_PERSISTED_QUOTE"
    assert position["strategy_id"] is None
    assert position["strategy_provenance"] == "UNAVAILABLE_UPSTREAM_STRATEGY_NOT_BOUND_TO_PHASE15_INTENT"
    assert position["reconciliation_state"] == "ENTRY_EVIDENCE_PRESENT_RECONCILIATION_AFTER_ENTRY_NOT_IMPLIED"
    assert payload["account"]["snapshot_kind"] == "LAST_RECONCILED_PRE_SUBMIT"
    assert payload["statistics"]["net_realized_pnl"] is None
    assert payload["statistics"]["net_realized_pnl_state"] == "UNAVAILABLE_PHASE15_OUTCOME_SCHEMA_IS_GROSS_ONLY"


def test_paper_dashboard_stale_quote_cannot_create_marked_pnl(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    _write_attempt_manifest(settings, _attempt(DiscoveryDirection.BULLISH))
    _write_live_state(settings, bid=120.0, ask=120.1, provider_timestamp=NOW - timedelta(seconds=31))
    payload = PaperDashboardService(settings, now_utc=lambda: NOW).snapshot()
    position = payload["open_positions"][0]
    assert position["current_mark"] is None
    assert position["unrealized_pnl"] is None
    assert position["unrealized_return"] is None
    assert position["mark_state"] == "UNAVAILABLE"
    assert payload["health"]["fresh_mark_count"] == 0


def test_paper_dashboard_provider_uncertainty_is_degraded_without_attempt_artifact(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    root = settings.resolved_path(settings.data.paths.derived) / "execution" / "phase15" / "v1"
    _write_json(
        root / "manifests" / "2026" / "2026-09-03.json",
        {
            "as_of_date": "2026-09-03",
            "generated_at_utc": NOW.isoformat(),
            "selected_environment": "paper",
            "selected_broker": "webull",
            "record_count": 1,
            "blocked_count": 0,
            "paper_submitted_count": 0,
            "existing_reconciled_count": 0,
            "provider_uncertain_count": 1,
            "requires_reconciliation": True,
            "pass": False,
            "records": [
                {
                    "ticker": "XYZ",
                    "as_of_date": "2026-09-03",
                    "environment": "paper",
                    "broker": "webull",
                    "disposition": "PROVIDER_SUBMISSION_UNCERTAIN",
                    "reason_codes": ["RECONCILIATION_REQUIRED"],
                    "provider_submission_attempted": True,
                    "provider_submission_uncertain": True,
                }
            ],
        },
    )
    payload = PaperDashboardService(settings, now_utc=lambda: NOW).snapshot()
    assert payload["status"] == "DEGRADED"
    assert payload["open_positions"] == []
    assert payload["health"]["provider_submission_uncertain"] is True
    assert payload["health"]["requires_reconciliation"] is True


class _FakeObservabilityService:
    def snapshot(self):
        return {"status": "LOCAL_TEST", "provider_reads": 0, "provider_writes": 0}


class _FakePaperDashboardService:
    def __init__(self) -> None:
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        return {
            "contract_version": "test-paper-dashboard",
            "status": "NOT_RUN",
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_writes": 0,
        }


def test_phase19_paper_dashboard_endpoint_and_bundle_are_local_read_only(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)

    def forbidden_broker_factory(_broker):
        raise AssertionError("paper-dashboard GET must not initialize a broker")

    status_service = Phase16StatusService(settings, env={}, broker_factory=forbidden_broker_factory)
    paper_service = _FakePaperDashboardService()
    server = create_phase19_status_server(
        service=status_service,
        observability_service=_FakeObservabilityService(),
        paper_dashboard_service=paper_service,
        host="127.0.0.1",
        port=0,
        web_root=settings.project_root / "apps" / "web",
    )
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        with urlopen(f"http://{host}:{port}/api/v1/ops/paper-dashboard", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "NOT_RUN"
        assert payload["provider_reads"] == 0
        assert payload["broker_writes"] == 0
        assert paper_service.calls == 1

        with urlopen(f"http://{host}:{port}/assets/observability.js", timeout=2) as response:
            bundle = response.read().decode("utf-8")
        assert "/api/v1/ops/paper-dashboard" in bundle
        assert "atlas:observability-refreshed" in bundle
        assert "window.refreshPaperDashboard" in bundle
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_paper_dashboard_browser_uses_existing_local_refresh_timer_only() -> None:
    settings = load_settings()
    web_root = settings.project_root / "apps" / "web"
    paper_js = (web_root / "paper_dashboard.js").read_text(encoding="utf-8")
    controls_js = (web_root / "observability_controls.js").read_text(encoding="utf-8")

    assert "/api/v1/ops/paper-dashboard" in paper_js
    assert "method: \"GET\"" in paper_js
    assert "setInterval" not in paper_js
    assert "method: \"POST\"" not in paper_js
    assert "/api/v1/operations/" not in paper_js
    assert "refresh=1" not in paper_js
    assert "atlas:observability-refreshed" in paper_js
    assert controls_js.count("window.setInterval") == 1
    assert "atlas:observability-refreshed" in controls_js
    assert "No automatic broker refresh · no mutation authority" in controls_js
