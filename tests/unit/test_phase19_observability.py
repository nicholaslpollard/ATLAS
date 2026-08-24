from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.control_plane.phase19_observability import Phase19ObservabilityService
from packages.control_plane.phase19_policy import phase19_policy_fingerprint
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path, "live": tmp_path / "live"})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


class _PublicSystem:
    def model_dump(self, *, mode: str):
        assert mode == "json"
        return {
            "health": "HEALTHY",
            "selected_broker": "webull",
            "selected_environment": "paper",
            "provider_write_uncertain": False,
        }


class _FakeStatusService:
    def system_status(self):
        return _PublicSystem()


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_realtime_live_state(settings) -> None:
    _write_json(
        MarketDataPaths(settings).live_state_file(),
        {
            "generated_at_utc": "2026-08-24T14:00:00+00:00",
            "feed_mode": "realtime",
            "expected_delay_seconds": 0,
            "connection_state": "subscribed",
            "subscriptions": ["Q.AAPL"],
            "session": {
                "as_of_utc": "2026-08-24T14:00:00+00:00",
                "local_date": "2026-08-24",
                "is_exchange_session": True,
                "session_segment": "regular",
                "regular_open_utc": "2026-08-24T13:30:00+00:00",
                "regular_close_utc": "2026-08-24T20:00:00+00:00",
                "next_session_date": "2026-08-25",
                "next_regular_open_utc": "2026-08-25T13:30:00+00:00",
            },
            "received_events": 10,
            "accepted_events": 9,
            "ignored_out_of_order_events": 1,
            "parse_errors": 0,
            "reconnects": 0,
            "restored_symbol_count": 0,
            "observed_symbol_count": 1,
            "last_received_at_utc": "2026-08-24T14:00:00+00:00",
            "transport_gaps": [],
            "open_transport_gap_started_at_utc": None,
            "symbols": [
                {
                    "symbol": "AAPL",
                    "as_of_utc": "2026-08-24T14:00:00+00:00",
                    "minute": None,
                    "minute_freshness": "unknown",
                    "quote_freshness": "fresh",
                    "quote": {
                        "symbol": "AAPL",
                        "provider_timestamp_utc": "2026-08-24T13:59:59+00:00",
                        "session_date": "2026-08-24",
                        "session_segment": "regular",
                        "bid_price": 200.0,
                        "bid_size": 10,
                        "ask_price": 200.1,
                        "ask_size": 11,
                        "sequence": 1,
                        "feed_mode": "realtime",
                        "expected_delay_seconds": 0,
                        "received_at_utc": "2026-08-24T14:00:00+00:00",
                    },
                }
            ],
        },
    )


def test_observability_reads_existing_artifacts_without_sensitive_identifiers(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    candidate_root = tmp_path / "candidates" / "phase11" / "v1"
    candidate_manifest = candidate_root / "manifests" / "2026" / "2026-08-14.json"
    _write_json(
        candidate_manifest,
        {
            "as_of_date": "2026-08-14",
            "generated_at_utc": "2026-08-14T21:00:00+00:00",
            "considered_warm_hot_directional": 1,
            "promoted_count": 0,
            "promoted_tickers": [],
            "dependency_fingerprint": "d" * 64,
            "lineage": {"accepted_ml_model_id": "mlmodel-test"},
        },
    )
    candidate_path = candidate_root / "year=2026" / "date=2026-08-14" / "all.jsonl"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(
            {
                "instrument_id": "secret-internal-instrument-id",
                "ticker": "AAPL",
                "as_of_date": "2026-08-14",
                "discovery_effective_state": "hot",
                "discovery_direction": "bullish",
                "discovery_priority_score": 0.81,
                "market_state": "risk_on",
                "sector_state": "technology",
                "ticker_state": "trend",
                "ml_probability_evidence": {
                    "model_id": "mlmodel-test",
                    "p_down": 0.2,
                    "p_neutral": 0.3,
                    "p_up": 0.5,
                },
                "supported_fired_strategy_ids": [],
                "promoted": False,
                "reason_codes": ["NO_SUPPORTED_FIRED_STRATEGY"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _write_json(
        tmp_path / "ai_review" / "phase14" / "v1" / "manifests" / "2026" / "2026-08-14.json",
        {
            "as_of_date": "2026-08-14",
            "generated_at_utc": "2026-08-14T21:05:00+00:00",
            "phase13_review_ready_count": 0,
            "ai_review_count": 0,
            "disposition_counts": {"APPROVE": 0, "CAUTIOUS": 0, "REJECT": 0},
            "records": [],
            "no_review_disposition": "NO_ACCEPTED_PHASE13_REVIEW_READY_CASES",
            "source_fingerprint": "a" * 64,
        },
    )

    outcome = tmp_path / "execution" / "phase15" / "v1" / "outcomes" / "year=2026" / "x" / "outcome.json"
    _write_json(
        outcome,
        {
            "intent_id": "intent-that-is-not-public",
            "account_id": "raw-account-id-that-must-not-leak",
            "provider_order_id": "provider-order-id-that-must-not-leak",
            "broker": "webull",
            "environment": "paper",
            "ticker": "MSFT",
            "direction": "bullish",
            "quantity": 1.0,
            "opened_at_utc": "2026-08-14T14:00:00+00:00",
            "closed_at_utc": "2026-08-14T15:00:00+00:00",
            "exit_reason": "target",
            "gross_pnl": 12.5,
            "gross_return": 0.01,
            "realized_r": 1.2,
            "descriptive_only": True,
        },
    )
    _write_realtime_live_state(settings)

    service = Phase19ObservabilityService(
        settings,
        status_service=_FakeStatusService(),
        now_utc=lambda: datetime(2026, 8, 24, 14, 0, 5, tzinfo=UTC),
    )
    payload = service.snapshot()

    assert payload["phase"]["stacked_phase_state"] == "STACKED_PREP_GREEN"
    assert payload["authority"]["provider_reads"] == 0
    assert payload["authority"]["provider_writes"] == 0
    assert payload["authority"]["live_execution_promoted"] is False
    assert payload["authority"]["automatic_cross_broker_failover_allowed"] is False
    assert payload["authority"]["artifact_recency_diagnostic_only"] is True
    assert payload["authority"]["live_market_state_diagnostic_only"] is True
    assert payload["authority"]["phase19_policy_fingerprint"] == phase19_policy_fingerprint()
    assert payload["candidates"]["considered_count"] == 1
    assert payload["candidates"]["candidates"][0]["ticker"] == "AAPL"
    assert payload["candidates"]["candidates"][0]["sector_state"] == "technology"
    assert payload["candidates"]["recency_state"] == "OLDER"
    assert payload["ai_audit"]["recency_state"] == "OLDER"
    assert payload["artifact_recency"]["diagnostic_only"] is True
    assert payload["outcomes"]["outcome_count"] == 1
    assert payload["outcomes"]["winning_count"] == 1
    assert payload["outcomes"]["losing_count"] == 0
    assert payload["outcomes"]["flat_count"] == 0
    assert payload["outcomes"]["win_rate"] == 1.0
    assert payload["outcomes"]["total_gross_pnl"] == 12.5
    assert payload["outcomes"]["average_realized_r"] == 1.2

    live = payload["live_market"]
    assert live["available"] is True
    assert live["snapshot_age_seconds"] == 5.0
    assert live["feed_mode"] == "realtime"
    assert live["expected_delay_seconds"] == 0
    assert live["connection_state"] == "subscribed"
    assert live["subscriptions"] == ["Q.AAPL"]
    assert live["session"]["session_segment"] == "regular"
    assert live["open_transport_gap"] is False
    assert live["phase18_market_inputs"] == {
        "diagnostic_only": True,
        "state": "INPUTS_APPEAR_READY",
        "quote_age_cap_seconds": 30,
        "snapshot_within_quote_age_cap": True,
        "subscribed": True,
        "realtime": True,
        "delay_zero": True,
        "no_open_transport_gap": True,
        "regular_session": True,
        "has_fresh_quote_within_age_cap": True,
    }
    assert live["quotes"][0]["ticker"] == "AAPL"
    assert live["quotes"][0]["bid_price"] == 200.0
    assert live["quotes"][0]["ask_price"] == 200.1
    assert live["quotes"][0]["provider_age_seconds"] == 6.0
    assert payload["pipeline"]["live_market_state"]["phase18_input_state"] == "INPUTS_APPEAR_READY"

    serialized = json.dumps(payload, sort_keys=True)
    assert "secret-internal-instrument-id" not in serialized
    assert "raw-account-id-that-must-not-leak" not in serialized
    assert "provider-order-id-that-must-not-leak" not in serialized
    assert "intent-that-is-not-public" not in serialized


def test_old_live_snapshot_cannot_appear_phase18_ready(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    _write_realtime_live_state(settings)
    service = Phase19ObservabilityService(
        settings,
        status_service=_FakeStatusService(),
        now_utc=lambda: datetime(2026, 8, 24, 14, 2, 0, tzinfo=UTC),
    )
    payload = service.snapshot()
    inputs = payload["live_market"]["phase18_market_inputs"]
    assert inputs["snapshot_within_quote_age_cap"] is False
    assert inputs["has_fresh_quote_within_age_cap"] is False
    assert inputs["state"] == "NOT_READY"


def test_missing_observability_artifacts_are_explicit_not_synthesized(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    service = Phase19ObservabilityService(
        settings,
        status_service=_FakeStatusService(),
        now_utc=lambda: datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )
    payload = service.snapshot()

    assert payload["candidates"] == {
        "available": False,
        "as_of_date": None,
        "generated_at_utc": None,
        "age_hours": None,
        "recency_state": "UNKNOWN",
        "considered_count": 0,
        "promoted_count": 0,
        "candidates": [],
        "reason": "CANDIDATE_ARTIFACTS_UNAVAILABLE",
    }
    assert payload["ai_audit"]["available"] is False
    assert payload["ai_audit"]["reason"] == "AI_REVIEW_ARTIFACTS_UNAVAILABLE"
    assert payload["ai_audit"]["recency_state"] == "UNKNOWN"
    assert payload["outcomes"]["available"] is False
    assert payload["outcomes"]["reason"] == "EXECUTION_OUTCOMES_UNAVAILABLE"
    assert payload["outcomes"]["win_rate"] is None
    assert payload["live_market"]["available"] is False
    assert payload["live_market"]["reason"] == "LIVE_MARKET_STATE_UNAVAILABLE"
    assert payload["live_market"]["phase18_market_inputs"]["state"] == "UNAVAILABLE"
    assert payload["pipeline"]["live_market_state"]["available"] is False
    assert payload["pipeline"]["candidate_materialization"]["available"] is False
    assert payload["artifact_recency"]["candidate_materialization"]["state"] == "UNKNOWN"
