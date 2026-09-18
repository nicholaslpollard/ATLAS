from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.simulation.current_live_evidence import (
    CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentLiveEvidenceError,
    capture_current_live_evidence_v1,
    current_live_evidence_payload,
)


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _snapshot_payload(*, generated: str, quote: bool) -> dict[str, object]:
    symbol = {
        "symbol": "AAPL",
        "as_of_utc": generated,
        "minute": {
            "symbol": "AAPL",
            "bar_start_utc": "2026-09-18T19:59:00+00:00",
            "bar_end_utc": "2026-09-18T20:00:00+00:00",
            "session_date": "2026-09-18",
            "session_segment": "regular",
            "open": 200.0,
            "high": 201.0,
            "low": 199.5,
            "close": 200.5,
            "volume": 1000.0,
            "feed_mode": "delayed",
            "expected_delay_seconds": 900,
            "received_at_utc": "2026-09-18T20:15:01+00:00",
        },
        "minute_freshness": "fresh",
        "quote": None,
        "quote_freshness": "unknown",
    }
    if quote:
        symbol["quote"] = {
            "symbol": "AAPL",
            "provider_timestamp_utc": "2026-09-18T20:14:59+00:00",
            "session_date": "2026-09-18",
            "session_segment": "regular",
            "bid_price": 200.4,
            "bid_size": 10,
            "ask_price": 200.6,
            "ask_size": 12,
            "sequence": 1,
            "feed_mode": "delayed",
            "expected_delay_seconds": 900,
            "received_at_utc": "2026-09-18T20:15:01+00:00",
        }
        symbol["quote_freshness"] = "fresh"
    return {
        "generated_at_utc": generated,
        "feed_mode": "delayed",
        "expected_delay_seconds": 900,
        "connection_state": "subscribed",
        "subscriptions": ["AM.*"],
        "session": {
            "as_of_utc": generated,
            "local_date": "2026-09-18",
            "is_exchange_session": True,
            "session_segment": "regular",
            "regular_open_utc": "2026-09-18T13:30:00+00:00",
            "regular_close_utc": "2026-09-18T20:00:00+00:00",
            "next_session_date": "2026-09-21",
            "next_regular_open_utc": "2026-09-21T13:30:00+00:00",
        },
        "received_events": 10,
        "accepted_events": 10,
        "ignored_out_of_order_events": 0,
        "parse_errors": 0,
        "reconnects": 0,
        "restored_symbol_count": 0,
        "observed_symbol_count": 1,
        "last_received_at_utc": "2026-09-18T20:15:01+00:00",
        "transport_gaps": [],
        "open_transport_gap_started_at_utc": None,
        "symbols": [symbol],
    }


def _write_snapshot(settings, payload) -> None:
    path = MarketDataPaths(settings).live_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_current_live_evidence_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT
        == "6502f8b9a4644705ec819bf7ecfcc3ee8b65742f4016454e497b0da8aca5deb0"
    )


def test_current_live_evidence_hashes_and_validates_local_snapshot(tmp_path) -> None:
    settings = _settings(tmp_path)
    _write_snapshot(
        settings,
        _snapshot_payload(
            generated="2026-09-18T20:15:02+00:00",
            quote=True,
        ),
    )
    evidence = capture_current_live_evidence_v1(
        settings,
        captured_at_utc=datetime(
            2026, 9, 18, 20, 15, 5, tzinfo=UTC
        ),
    )
    payload = current_live_evidence_payload(evidence)

    assert evidence.snapshot_age_seconds == pytest.approx(3.0)
    assert evidence.minute_symbol_count == 1
    assert evidence.quote_symbol_count == 1
    assert evidence.fresh_minute_symbol_count == 1
    assert evidence.fresh_quote_symbol_count == 1
    assert payload["minute_to_quote_fabrication"] is False
    assert payload["network_provider_calls_performed"] == 0
    assert payload["network_broker_calls_performed"] == 0
    assert payload["authority"]["paper_authority"] is False
    assert len(evidence.source_sha256) == 64
    assert len(evidence.evidence_fingerprint) == 64


def test_minute_only_snapshot_remains_quote_less(tmp_path) -> None:
    settings = _settings(tmp_path)
    _write_snapshot(
        settings,
        _snapshot_payload(
            generated="2026-09-18T20:15:02+00:00",
            quote=False,
        ),
    )
    evidence = capture_current_live_evidence_v1(
        settings,
        captured_at_utc=datetime(
            2026, 9, 18, 20, 15, 5, tzinfo=UTC
        ),
    )
    assert evidence.minute_symbol_count == 1
    assert evidence.quote_symbol_count == 0
    assert evidence.fresh_quote_symbol_count == 0
    assert evidence.minute_only_symbol_count == 1


def test_future_snapshot_fails_closed(tmp_path) -> None:
    settings = _settings(tmp_path)
    payload = _snapshot_payload(
        generated="2026-09-18T20:16:00+00:00",
        quote=False,
    )
    payload["last_received_at_utc"] = "2026-09-18T20:16:00+00:00"
    _write_snapshot(settings, payload)

    with pytest.raises(
        CurrentLiveEvidenceError,
        match="after capture time",
    ):
        capture_current_live_evidence_v1(
            settings,
            captured_at_utc=datetime(
                2026, 9, 18, 20, 15, 5, tzinfo=UTC
            ),
        )


def test_event_feed_lineage_mismatch_fails_closed(tmp_path) -> None:
    settings = _settings(tmp_path)
    payload = _snapshot_payload(
        generated="2026-09-18T20:15:02+00:00",
        quote=False,
    )
    payload["symbols"][0]["minute"]["expected_delay_seconds"] = 0
    _write_snapshot(settings, payload)

    with pytest.raises(
        CurrentLiveEvidenceError,
        match="delay does not match snapshot",
    ):
        capture_current_live_evidence_v1(
            settings,
            captured_at_utc=datetime(
                2026, 9, 18, 20, 15, 5, tzinfo=UTC
            ),
        )
