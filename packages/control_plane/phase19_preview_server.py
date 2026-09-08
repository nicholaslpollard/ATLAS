from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PHASE19_PREVIEW_CONTRACT_VERSION = "a34.5-codespaces-preview-v1-synthetic-read-only"
DEFAULT_PHASE19_PREVIEW_HOST = "0.0.0.0"
DEFAULT_PHASE19_PREVIEW_PORT = 8765
MAX_PREVIEW_ASSET_BYTES = 2 * 1024 * 1024

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WEB_ROOT = (_PROJECT_ROOT / "apps" / "web").resolve()

_STATIC_ASSETS = {
    "/": ("phase19.html", "text/html; charset=utf-8"),
    "/index.html": ("phase19.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assets/observability.css": ("observability.css", "text/css; charset=utf-8"),
}
_PREVIEW_JS_BUNDLE = (
    "observability.js",
    "observability_controls.js",
    "paper_dashboard.js",
    "phase19_preview.js",
)

_CSP = (
    "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _catalog_payload() -> dict[str, Any]:
    rows = [
        ("ma_trend_cross_50_200_long_v1", "moving_average_trend", "long"),
        ("ema_pullback_20_50_long_v1", "pullback_continuation", "long"),
        ("macd_shift_12_26_9_long_v1", "momentum", "long"),
        ("macd_shift_12_26_9_short_v1", "momentum", "short"),
        ("rsi_recovery_14_trend_long_v1", "mean_reversion", "long"),
        ("donchian_breakout_20_volume_long_v1", "price_breakout", "long"),
        ("donchian_breakout_20_volume_short_v1", "price_breakout", "short"),
        ("bollinger_squeeze_breakout_20_long_v1", "volatility_expansion", "long"),
        ("bollinger_squeeze_breakout_20_short_v1", "volatility_expansion", "short"),
    ]
    return {
        "contract_version": "preview-reference-catalog",
        "family_count": 6,
        "strategy_count": len(rows),
        "strategies": [
            {
                "specification": {
                    "strategy_id": strategy_id,
                    "family": family,
                    "direction": direction,
                },
                "authority": {
                    "authority": "RESEARCH",
                    "evidence_source": "PRACTITIONER_BASELINE",
                },
            }
            for strategy_id, family, direction in rows
        ],
        "preview_synthetic": True,
    }


def _replay_payload() -> dict[str, Any]:
    strategy_stats = {
        "ma_trend_cross_50_200_long_v1": {"signals": 24, "admitted": 6, "completed": 6, "net_pnl": 840.0},
        "ema_pullback_20_50_long_v1": {"signals": 31, "admitted": 8, "completed": 8, "net_pnl": 1120.0},
        "macd_shift_12_26_9_long_v1": {"signals": 18, "admitted": 4, "completed": 4, "net_pnl": -180.0},
        "macd_shift_12_26_9_short_v1": {"signals": 16, "admitted": 0, "completed": 0, "net_pnl": 0.0},
        "rsi_recovery_14_trend_long_v1": {"signals": 22, "admitted": 5, "completed": 5, "net_pnl": 515.0},
        "donchian_breakout_20_volume_long_v1": {"signals": 14, "admitted": 4, "completed": 4, "net_pnl": 660.0},
        "donchian_breakout_20_volume_short_v1": {"signals": 11, "admitted": 0, "completed": 0, "net_pnl": 0.0},
        "bollinger_squeeze_breakout_20_long_v1": {"signals": 17, "admitted": 4, "completed": 4, "net_pnl": 245.0},
        "bollinger_squeeze_breakout_20_short_v1": {"signals": 13, "admitted": 0, "completed": 0, "net_pnl": 0.0},
    }
    return {
        "status": "AVAILABLE",
        "message": "SYNTHETIC CODESPACES PREVIEW — layout demonstration only; not ATLAS evidence.",
        "preview_synthetic": True,
        "artifact_integrity": {
            "all_sha256_verified": False,
            "verified_artifacts": 0,
            "expected_artifacts": 0,
        },
        "summary": {
            "total_return": 0.031,
            "maximum_drawdown": -0.012,
            "final_equity": 103100.0,
            "total_transaction_cost": 78.0,
            "completed_positions": 31,
            "admitted_positions": 31,
            "summary_by_strategy": strategy_stats,
        },
        "recent_position_outcomes": [
            {
                "exit_session": "2026-05-07",
                "ticker": "MSFT",
                "family": "pullback_continuation",
                "strategy_id": "ema_pullback_20_50_long_v1",
                "exit_reason": "TARGET",
                "net_return_on_entry_notional": 0.018,
                "net_pnl": 320.0,
            },
            {
                "exit_session": "2026-05-08",
                "ticker": "AMD",
                "family": "momentum",
                "strategy_id": "macd_shift_12_26_9_long_v1",
                "exit_reason": "STOP",
                "net_return_on_entry_notional": -0.007,
                "net_pnl": -125.0,
            },
        ],
        "recent_portfolio_decisions": [
            {
                "requested_entry_session": "2026-05-08",
                "ticker": "MSFT",
                "family": "pullback_continuation",
                "status": "ADMITTED",
                "admitted_quantity": 25,
                "admitted_notional": 10400.0,
                "reason_codes": ["FAMILY_LOAD_OK", "RISK_WITHIN_LIMIT"],
            },
            {
                "requested_entry_session": "2026-05-09",
                "ticker": "NVDA",
                "family": "price_breakout",
                "status": "REJECTED",
                "admitted_quantity": 0,
                "admitted_notional": 0.0,
                "reason_codes": ["POSITION_LIMIT"],
            },
        ],
        "recent_simulated_orders": [
            {
                "session": "2026-05-08",
                "ticker": "MSFT",
                "kind": "ENTRY",
                "timing": "NEXT_OPEN",
                "quantity": 25,
                "price": 416.0,
                "transaction_cost": 5.2,
                "cash_after": 89594.8,
            },
            {
                "session": "2026-05-09",
                "ticker": "MSFT",
                "kind": "EXIT",
                "timing": "TARGET",
                "quantity": 25,
                "price": 429.0,
                "transaction_cost": 5.36,
                "cash_after": 100314.44,
            },
        ],
        "equity_curve_tail": [
            {"session": "2026-05-04", "equity": 100000.0, "gross_exposure_fraction": 0.10, "open_positions": 1},
            {"session": "2026-05-05", "equity": 100720.0, "gross_exposure_fraction": 0.22, "open_positions": 2},
            {"session": "2026-05-06", "equity": 100410.0, "gross_exposure_fraction": 0.18, "open_positions": 2},
            {"session": "2026-05-07", "equity": 102240.0, "gross_exposure_fraction": 0.12, "open_positions": 1},
            {"session": "2026-05-08", "equity": 103100.0, "gross_exposure_fraction": 0.00, "open_positions": 0},
        ],
    }


def _status_payload(now: datetime) -> dict[str, Any]:
    as_of = _iso(now - timedelta(seconds=3))
    return {
        "preview_synthetic": True,
        "system": {
            "health": "HEALTHY",
            "runtime_state_valid": True,
            "action_ledger_valid": True,
            "provider_write_uncertain": False,
            "selected_broker": "webull",
            "selected_environment": "paper",
            "runtime_state_source": "CODESPACES_SYNTHETIC_PREVIEW",
            "runtime_revision": 1,
            "action_count": 0,
            "active_action_count": 0,
            "uncertain_action_count": 0,
            "accepted_phase15_merge_sha": "PREVIEW_ONLY",
            "accepted_phase15_policy_fingerprint": "PREVIEW_ONLY",
            "phase16_policy_fingerprint": "PREVIEW_ONLY",
            "phase15": {
                "accepted": True,
                "as_of_date": "2026-09-04",
                "execution_case_count": 3,
                "policy_fingerprint": "PREVIEW_ONLY",
                "cumulative_foundation_fingerprint": "PREVIEW_ONLY",
            },
        },
        "brokers": [
            {
                "broker": "webull",
                "state": "AVAILABLE",
                "credentials": {"ready": True},
                "account": {"account_ref": "PREVIEW-WEBULL", "equity": 100325.44},
                "open_orders": [],
                "positions": [
                    {"ticker": "AAPL", "quantity": 10, "market_value": 2291.2}
                ],
                "reconciled": True,
                "safe_to_switch_broker": False,
                "as_of_utc": as_of,
            },
            {
                "broker": "alpaca",
                "state": "AVAILABLE",
                "credentials": {"ready": True},
                "account": {"account_ref": "PREVIEW-ALPACA", "equity": 100000.0},
                "open_orders": [],
                "positions": [],
                "reconciled": True,
                "safe_to_switch_broker": True,
                "as_of_utc": as_of,
            },
        ],
    }


def _observability_payload(now: datetime) -> dict[str, Any]:
    generated = _iso(now)
    quote_time = _iso(now - timedelta(seconds=2))
    return {
        "preview_synthetic": True,
        "generated_at_utc": generated,
        "phase": {
            "stacked_phase": "19",
            "stacked_phase_state": "STACKED_PREP_GREEN",
            "stacked_phase_name": "Operations Dashboard & Paper/Shadow Observability",
            "merge_authoritative_phase": "18B",
            "merge_authoritative_state": "ACCEPTED",
        },
        "authority": {
            "mode": "CODESPACES_PREVIEW_SYNTHETIC",
            "provider_reads": 0,
            "provider_writes": 0,
            "live_execution_promoted": False,
        },
        "artifact_recency": {
            "candidate_materialization": {"state": "RECENT", "age_hours": 0.02},
            "ai_audit": {"state": "RECENT", "age_hours": 0.03},
        },
        "pipeline": {
            "live_market_state": {"available": True, "count": 2, "as_of_date": "2026-09-04", "phase18_input_state": "INPUTS_APPEAR_READY"},
            "candidate_materialization": {"available": True, "count": 3, "as_of_date": "2026-09-04", "recency_state": "RECENT", "age_hours": 0.02},
            "ai_audit": {"available": True, "count": 3, "as_of_date": "2026-09-04", "recency_state": "RECENT", "age_hours": 0.03},
            "execution_outcomes": {"available": True, "count": 2, "as_of_date": "2026-09-04"},
        },
        "live_market": {
            "available": True,
            "connection_state": "SUBSCRIBED",
            "feed_mode": "realtime",
            "expected_delay_seconds": 0,
            "snapshot_age_seconds": 2.0,
            "accepted_events": 1842,
            "received_events": 1842,
            "parse_errors": 0,
            "reconnects": 0,
            "session": {"session_segment": "regular", "local_date": "2026-09-04"},
            "phase18_market_inputs": {
                "state": "INPUTS_APPEAR_READY",
                "snapshot_within_quote_age_cap": True,
                "subscribed": True,
                "realtime": True,
                "delay_zero": True,
                "no_open_transport_gap": True,
                "regular_session": True,
                "has_fresh_quote_within_age_cap": True,
            },
            "quotes": [
                {
                    "ticker": "AAPL",
                    "quote_freshness": "FRESH",
                    "bid_price": 229.12,
                    "ask_price": 229.15,
                    "session_segment": "regular",
                    "feed_mode": "realtime",
                    "provider_timestamp_utc": quote_time,
                    "received_at_utc": generated,
                },
                {
                    "ticker": "NVDA",
                    "quote_freshness": "FRESH",
                    "bid_price": 184.41,
                    "ask_price": 184.45,
                    "session_segment": "regular",
                    "feed_mode": "realtime",
                    "provider_timestamp_utc": quote_time,
                    "received_at_utc": generated,
                },
            ],
        },
        "candidates": {
            "available": True,
            "as_of_date": "2026-09-04",
            "generated_at_utc": generated,
            "recency_state": "RECENT",
            "age_hours": 0.02,
            "considered_count": 3,
            "promoted_count": 1,
            "accepted_ml_model_id": "PREVIEW_CALIBRATED_MODEL",
            "candidates": [
                {
                    "ticker": "AAPL",
                    "as_of_date": "2026-09-04",
                    "discovery_state": "HOT",
                    "direction": "bullish",
                    "priority_score": 0.86,
                    "market_state": "RISK_ON",
                    "sector_state": "UNAVAILABLE",
                    "ticker_state": "UNAVAILABLE",
                    "p_up": 0.64,
                    "p_neutral": 0.20,
                    "p_down": 0.16,
                    "ml_model_id": "PREVIEW_CALIBRATED_MODEL",
                    "supported_fired_strategy_ids": ["ema_pullback_20_50_long_v1"],
                    "promoted": True,
                    "reason_codes": ["TREND_ALIGNED", "RISK_WITHIN_LIMIT"],
                },
                {
                    "ticker": "NVDA",
                    "as_of_date": "2026-09-04",
                    "discovery_state": "WARM",
                    "direction": "bullish",
                    "priority_score": 0.72,
                    "market_state": "RISK_ON",
                    "sector_state": "UNAVAILABLE",
                    "ticker_state": "UNAVAILABLE",
                    "p_up": 0.58,
                    "p_neutral": 0.24,
                    "p_down": 0.18,
                    "ml_model_id": "PREVIEW_CALIBRATED_MODEL",
                    "supported_fired_strategy_ids": ["donchian_breakout_20_volume_long_v1"],
                    "promoted": False,
                    "reason_codes": ["PORTFOLIO_CAPACITY_LIMIT"],
                },
                {
                    "ticker": "MSFT",
                    "as_of_date": "2026-09-04",
                    "discovery_state": "WATCH",
                    "direction": "neutral",
                    "priority_score": 0.41,
                    "market_state": "RISK_ON",
                    "sector_state": "UNAVAILABLE",
                    "ticker_state": "UNAVAILABLE",
                    "p_up": 0.39,
                    "p_neutral": 0.37,
                    "p_down": 0.24,
                    "ml_model_id": "PREVIEW_CALIBRATED_MODEL",
                    "supported_fired_strategy_ids": [],
                    "promoted": False,
                    "reason_codes": ["NO_AUTHORIZED_SETUP"],
                },
            ],
        },
        "ai_audit": {
            "available": True,
            "as_of_date": "2026-09-04",
            "review_count": 3,
            "disposition_counts": {"APPROVE": 1, "CAUTIOUS": 1, "REJECT": 1},
            "no_review_disposition": "Synthetic preview audit",
            "recency_state": "RECENT",
            "age_hours": 0.03,
        },
        "outcomes": {
            "outcome_count": 2,
            "total_gross_pnl": 412.5,
            "win_rate": 0.5,
            "winning_count": 1,
            "losing_count": 1,
            "flat_count": 0,
            "average_realized_r": 0.42,
            "latest_closed_at_utc": _iso(now - timedelta(hours=3)),
            "outcomes": [
                {
                    "ticker": "NVDA",
                    "broker": "webull",
                    "direction": "bullish",
                    "exit_reason": "TARGET",
                    "gross_pnl": 537.5,
                    "gross_return": 0.0215,
                    "realized_r": 1.48,
                    "closed_at_utc": _iso(now - timedelta(hours=3)),
                },
                {
                    "ticker": "AMD",
                    "broker": "webull",
                    "direction": "bullish",
                    "exit_reason": "STOP",
                    "gross_pnl": -125.0,
                    "gross_return": -0.0068,
                    "realized_r": -0.64,
                    "closed_at_utc": _iso(now - timedelta(days=1)),
                },
            ],
        },
    }


def _paper_dashboard_payload(now: datetime) -> dict[str, Any]:
    return {
        "contract_version": PHASE19_PREVIEW_CONTRACT_VERSION,
        "preview_synthetic": True,
        "generated_at_utc": _iso(now),
        "status": "AVAILABLE",
        "read_only": True,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_writes": 0,
        "manifest": {
            "as_of_date": "2026-09-04",
            "generated_at_utc": _iso(now - timedelta(seconds=5)),
            "selected_environment": "paper",
            "selected_broker": "webull",
            "record_count": 3,
            "blocked_count": 1,
            "paper_submitted_count": 1,
            "existing_reconciled_count": 0,
            "provider_uncertain_count": 0,
            "requires_reconciliation": False,
            "pass": True,
        },
        "account": {
            "broker": "webull",
            "environment": "paper",
            "as_of_utc": _iso(now - timedelta(seconds=8)),
            "equity": 100325.44,
            "cash": 77334.24,
            "buying_power": 77334.24,
            "gross_market_value": 2291.20,
            "trading_blocked": False,
            "shorting_enabled": False,
            "snapshot_kind": "LAST_RECONCILED_PRE_SUBMIT",
        },
        "reconciled_positions": [],
        "open_positions": [
            {
                "intent_id": "PREVIEW-AAPL-001",
                "ticker": "AAPL",
                "direction": "bullish",
                "side": "buy",
                "quantity": 10,
                "entry_price": 227.50,
                "current_mark": 229.12,
                "unrealized_pnl": 16.20,
                "unrealized_return": 0.00712,
                "mark_state": "FRESH_PERSISTED_QUOTE",
                "mark_as_of_utc": _iso(now - timedelta(seconds=2)),
                "stop": 222.00,
                "target": 238.00,
                "proposed_loss_at_stop": 55.0,
                "submitted_at_utc": _iso(now - timedelta(hours=2)),
                "updated_at_utc": _iso(now - timedelta(seconds=6)),
                "order_status": "filled",
                "strategy_id": None,
                "strategy_provenance": "UNAVAILABLE_UPSTREAM_STRATEGY_NOT_BOUND_TO_PHASE15_INTENT",
                "decision_reason_codes": ["TREND_ALIGNED", "RISK_WITHIN_LIMIT"],
                "risk_reason_codes": ["POSITION_RISK_ACCEPTED"],
                "reconciliation_state": "ENTRY_EVIDENCE_PRESENT_RECONCILIATION_AFTER_ENTRY_NOT_IMPLIED",
            }
        ],
        "decisions": [
            {
                "ticker": "AAPL",
                "as_of_date": "2026-09-04",
                "environment": "paper",
                "broker": "webull",
                "disposition": "PAPER_SUBMITTED",
                "reason_codes": ["PROMOTED_BASELINE", "RISK_ACCEPTED"],
                "provider_submission_attempted": True,
                "provider_submission_uncertain": False,
            },
            {
                "ticker": "NVDA",
                "as_of_date": "2026-09-04",
                "environment": "paper",
                "broker": "webull",
                "disposition": "BLOCKED",
                "reason_codes": ["PORTFOLIO_CAPACITY_LIMIT"],
                "provider_submission_attempted": False,
                "provider_submission_uncertain": False,
            },
        ],
        "orders": [
            {
                "intent_id": "PREVIEW-AAPL-001",
                "ticker": "AAPL",
                "broker": "webull",
                "client_order_id": "PREVIEW-ONLY",
                "side": "buy",
                "status": "filled",
                "requested_quantity": 10,
                "filled_quantity": 10,
                "average_fill_price": 227.50,
                "submitted_at_utc": _iso(now - timedelta(hours=2)),
                "updated_at_utc": _iso(now - timedelta(hours=1, minutes=59)),
                "existing_order_reused": False,
                "provider_submission_performed": True,
            }
        ],
        "closed_trades": [
            {
                "intent_id": "PREVIEW-NVDA-CLOSED",
                "broker": "webull",
                "environment": "paper",
                "ticker": "NVDA",
                "direction": "bullish",
                "quantity": 15,
                "entry_fill_price": 180.20,
                "exit_fill_price": 184.45,
                "opened_at_utc": _iso(now - timedelta(days=2)),
                "closed_at_utc": _iso(now - timedelta(hours=3)),
                "exit_reason": "target",
                "gross_pnl": 63.75,
                "gross_return": 0.02358,
                "realized_r": 1.21,
                "pnl_basis": "PHASE15_REALIZED_GROSS_DESCRIPTIVE_ONLY",
            }
        ],
        "statistics": {
            "closed_trade_count": 1,
            "total_realized_gross_pnl": 63.75,
            "winning_trade_count": 1,
            "losing_trade_count": 0,
            "net_realized_pnl": None,
            "net_realized_pnl_state": "UNAVAILABLE_PHASE15_OUTCOME_SCHEMA_IS_GROSS_ONLY",
        },
        "health": {
            "local_evidence_valid": True,
            "provider_submission_uncertain": False,
            "requires_reconciliation": False,
            "fresh_mark_count": 2,
            "automatic_broker_refresh": False,
            "browser_mutation_authority": False,
            "live_execution_promoted": False,
        },
    }


def preview_payload(path: str, *, now_utc: datetime | None = None) -> dict[str, Any] | None:
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    if path == "/healthz":
        return {
            "contract_version": PHASE19_PREVIEW_CONTRACT_VERSION,
            "preview_synthetic": True,
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_writes": 0,
        }
    if path == "/api/v1/status/full":
        return _status_payload(now)
    if path == "/api/v1/actions":
        return {"actions": [], "preview_synthetic": True}
    if path == "/api/v1/strategies/reference":
        return _catalog_payload()
    if path == "/api/v1/research/reference-replay":
        return _replay_payload()
    if path == "/api/v1/observability":
        return _observability_payload(now)
    if path == "/api/v1/ops/paper-dashboard":
        return _paper_dashboard_payload(now)
    if path == "/api/v1/session":
        return {
            "preview_synthetic": True,
            "csrf_token": "PREVIEW_POSTS_ARE_DISABLED",
            "header_name": "X-ATLAS-PREVIEW-CSRF",
        }
    return None


def _read_asset(filename: str) -> bytes:
    path = (_WEB_ROOT / filename).resolve()
    if path.parent != _WEB_ROOT or not path.is_file():
        raise FileNotFoundError(filename)
    raw = path.read_bytes()
    if len(raw) > MAX_PREVIEW_ASSET_BYTES:
        raise ValueError(f"preview asset exceeds size cap: {filename}")
    return raw


class Phase19PreviewHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Phase19PreviewRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ATLAS-Preview"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: HTTPStatus, raw: bytes, content_type: str) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", _CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._send(status, raw, "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        split = urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        payload = preview_payload(path)
        if payload is not None:
            self._send_json(HTTPStatus.OK, payload)
            return
        if path == "/assets/observability.js":
            try:
                raw = b"\n".join(_read_asset(name) for name in _PREVIEW_JS_BUNDLE)
            except (OSError, ValueError):
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "PREVIEW_ASSET_UNAVAILABLE"})
                return
            self._send(HTTPStatus.OK, raw, "text/javascript; charset=utf-8")
            return
        asset = _STATIC_ASSETS.get(path)
        if asset is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "PREVIEW_NOT_FOUND"})
            return
        filename, content_type = asset
        try:
            raw = _read_asset(filename)
        except (OSError, ValueError):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "PREVIEW_ASSET_UNAVAILABLE"})
            return
        self._send(HTTPStatus.OK, raw, content_type)

    def do_POST(self) -> None:
        self._send_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {
                "error": "PREVIEW_READ_ONLY",
                "preview_synthetic": True,
                "provider_writes": 0,
                "broker_writes": 0,
            },
        )


def create_phase19_preview_server(
    *,
    host: str = DEFAULT_PHASE19_PREVIEW_HOST,
    port: int = DEFAULT_PHASE19_PREVIEW_PORT,
) -> Phase19PreviewHTTPServer:
    return Phase19PreviewHTTPServer((host, port), Phase19PreviewRequestHandler)
