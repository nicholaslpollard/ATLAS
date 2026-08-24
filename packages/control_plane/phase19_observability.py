from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.enums import LiveConnectionState, LiveFeedMode, LiveFreshness, SessionSegment
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.schemas.live_market import LiveStateSnapshot

from .phase19_policy import phase19_policy_fingerprint, phase19_policy_payload
from .status import Phase16StatusService


PHASE19_OBSERVABILITY_CONTRACT_VERSION = (
    "phase19-observability-v3-local-artifacts-live-market-candidates-ai-outcomes"
)
PHASE19_CANDIDATE_LIMIT = 50
PHASE19_OUTCOME_LIMIT = 20
PHASE19_LIVE_QUOTE_LIMIT = 20
PHASE19_RECENT_ARTIFACT_HOURS = 96.0


class Phase19ObservabilityError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase19ObservabilityError(f"JSON root must be an object: {path}")
    return payload


def _read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise Phase19ObservabilityError(f"JSONL row must be an object: {path}")
            rows.append(payload)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _latest_json(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    candidates = sorted(path for path in root.rglob("*.json") if path.is_file())
    return candidates[-1] if candidates else None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _recency(generated_at_utc: Any, *, now_utc: datetime) -> dict[str, Any]:
    generated = _parse_utc(generated_at_utc)
    if generated is None:
        return {"age_hours": None, "recency_state": "UNKNOWN"}
    age_hours = max(0.0, (now_utc - generated).total_seconds() / 3600.0)
    return {
        "age_hours": round(age_hours, 2),
        "recency_state": "RECENT" if age_hours <= PHASE19_RECENT_ARTIFACT_HOURS else "OLDER",
    }


def _public_candidate(row: dict[str, Any]) -> dict[str, Any]:
    ml = row.get("ml_probability_evidence")
    if not isinstance(ml, dict):
        ml = {}
    return {
        "ticker": row.get("ticker"),
        "as_of_date": row.get("as_of_date"),
        "discovery_state": row.get("discovery_effective_state"),
        "direction": row.get("discovery_direction"),
        "priority_score": row.get("discovery_priority_score"),
        "market_state": row.get("market_state"),
        "sector_state": row.get("sector_state"),
        "ticker_state": row.get("ticker_state"),
        "p_down": ml.get("p_down"),
        "p_neutral": ml.get("p_neutral"),
        "p_up": ml.get("p_up"),
        "ml_model_id": ml.get("model_id"),
        "supported_fired_strategy_ids": row.get("supported_fired_strategy_ids") or [],
        "promoted": bool(row.get("promoted")),
        "reason_codes": row.get("reason_codes") or [],
    }


def _public_outcome(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "broker": row.get("broker"),
        "environment": row.get("environment"),
        "ticker": row.get("ticker"),
        "direction": row.get("direction"),
        "quantity": row.get("quantity"),
        "opened_at_utc": row.get("opened_at_utc"),
        "closed_at_utc": row.get("closed_at_utc"),
        "exit_reason": row.get("exit_reason"),
        "gross_pnl": row.get("gross_pnl"),
        "gross_return": row.get("gross_return"),
        "realized_r": row.get("realized_r"),
        "descriptive_only": row.get("descriptive_only"),
    }


def _finite_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


class Phase19ObservabilityService:
    """Read-only view over accepted ATLAS local artifacts.

    The service intentionally does not initialize broker adapters or market-data clients.
    Missing downstream artifacts are represented as unavailable display state rather than
    guessed, synthesized, or treated as permission to create them.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        status_service: Phase16StatusService | None = None,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.status_service = status_service or Phase16StatusService(settings)
        self.derived = settings.resolved_path(settings.data.paths.derived)
        self.market_paths = MarketDataPaths(settings)
        self._now_utc = now_utc or (lambda: datetime.now(UTC))

    def _candidate_summary(self, *, now_utc: datetime) -> dict[str, Any]:
        manifest_path = _latest_json(self.derived / "candidates" / "phase11" / "v1" / "manifests")
        if manifest_path is None:
            return {
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
        manifest = _read_json(manifest_path)
        as_of_date = str(manifest.get("as_of_date") or "")
        if not as_of_date:
            raise Phase19ObservabilityError("candidate manifest missing as_of_date")
        all_path = (
            self.derived
            / "candidates"
            / "phase11"
            / "v1"
            / f"year={as_of_date[:4]}"
            / f"date={as_of_date}"
            / "all.jsonl"
        )
        rows = [
            _public_candidate(row)
            for row in _read_jsonl(all_path, limit=PHASE19_CANDIDATE_LIMIT)
        ]
        generated_at_utc = manifest.get("generated_at_utc")
        recency = _recency(generated_at_utc, now_utc=now_utc)
        return {
            "available": True,
            "as_of_date": as_of_date,
            "generated_at_utc": generated_at_utc,
            **recency,
            "considered_count": int(manifest.get("considered_warm_hot_directional") or len(rows)),
            "promoted_count": int(manifest.get("promoted_count") or 0),
            "promoted_tickers": manifest.get("promoted_tickers") or [],
            "accepted_ml_model_id": (manifest.get("lineage") or {}).get("accepted_ml_model_id")
            if isinstance(manifest.get("lineage"), dict)
            else None,
            "dependency_fingerprint": manifest.get("dependency_fingerprint"),
            "candidates": rows,
            "display_limit": PHASE19_CANDIDATE_LIMIT,
        }

    def _ai_summary(self, *, now_utc: datetime) -> dict[str, Any]:
        manifest_path = _latest_json(self.derived / "ai_review" / "phase14" / "v1" / "manifests")
        if manifest_path is None:
            return {
                "available": False,
                "as_of_date": None,
                "generated_at_utc": None,
                "age_hours": None,
                "recency_state": "UNKNOWN",
                "review_count": 0,
                "disposition_counts": {"APPROVE": 0, "CAUTIOUS": 0, "REJECT": 0},
                "reason": "AI_REVIEW_ARTIFACTS_UNAVAILABLE",
            }
        manifest = _read_json(manifest_path)
        records = manifest.get("records") if isinstance(manifest.get("records"), list) else []
        public_records = [
            {
                "ticker": item.get("ticker"),
                "disposition": item.get("disposition"),
                "provider": item.get("provider"),
                "model": item.get("model"),
            }
            for item in records
            if isinstance(item, dict)
        ]
        generated_at_utc = manifest.get("generated_at_utc")
        recency = _recency(generated_at_utc, now_utc=now_utc)
        return {
            "available": True,
            "as_of_date": manifest.get("as_of_date"),
            "generated_at_utc": generated_at_utc,
            **recency,
            "review_ready_count": int(manifest.get("phase13_review_ready_count") or 0),
            "review_count": int(manifest.get("ai_review_count") or 0),
            "disposition_counts": manifest.get("disposition_counts")
            or {"APPROVE": 0, "CAUTIOUS": 0, "REJECT": 0},
            "no_review_disposition": manifest.get("no_review_disposition"),
            "records": public_records[:PHASE19_CANDIDATE_LIMIT],
            "source_fingerprint": manifest.get("source_fingerprint"),
        }

    def _outcome_summary(self) -> dict[str, Any]:
        root = self.derived / "execution" / "phase15" / "v1" / "outcomes"
        paths = sorted(path for path in root.rglob("outcome.json") if path.is_file()) if root.is_dir() else []
        rows: list[dict[str, Any]] = []
        for path in paths:
            rows.append(_public_outcome(_read_json(path)))
        rows.sort(key=lambda row: str(row.get("closed_at_utc") or ""), reverse=True)

        pnl_values = [
            value for value in (_finite_float(row.get("gross_pnl")) for row in rows) if value is not None
        ]
        r_values = [
            value for value in (_finite_float(row.get("realized_r")) for row in rows) if value is not None
        ]
        winning_count = sum(1 for value in pnl_values if value > 0)
        losing_count = sum(1 for value in pnl_values if value < 0)
        flat_count = sum(1 for value in pnl_values if value == 0)
        measured_count = len(pnl_values)
        return {
            "available": bool(rows),
            "outcome_count": len(rows),
            "measured_pnl_count": measured_count,
            "winning_count": winning_count,
            "losing_count": losing_count,
            "flat_count": flat_count,
            "win_rate": (winning_count / measured_count) if measured_count else None,
            "total_gross_pnl": sum(pnl_values),
            "average_realized_r": (sum(r_values) / len(r_values)) if r_values else None,
            "latest_closed_at_utc": rows[0].get("closed_at_utc") if rows else None,
            "descriptive_only": True,
            "outcomes": rows[:PHASE19_OUTCOME_LIMIT],
            "display_limit": PHASE19_OUTCOME_LIMIT,
            "reason": None if rows else "EXECUTION_OUTCOMES_UNAVAILABLE",
        }

    def _live_market_summary(self, *, now_utc: datetime) -> dict[str, Any]:
        path = self.market_paths.live_state_file()
        if not path.is_file():
            return {
                "available": False,
                "generated_at_utc": None,
                "snapshot_age_seconds": None,
                "feed_mode": None,
                "expected_delay_seconds": None,
                "connection_state": None,
                "subscriptions": [],
                "session": None,
                "received_events": 0,
                "accepted_events": 0,
                "ignored_out_of_order_events": 0,
                "parse_errors": 0,
                "reconnects": 0,
                "restored_symbol_count": 0,
                "observed_symbol_count": 0,
                "symbol_count": 0,
                "transport_gap_count": 0,
                "open_transport_gap": False,
                "last_received_at_utc": None,
                "phase18_market_inputs": {
                    "diagnostic_only": True,
                    "state": "UNAVAILABLE",
                    "quote_age_cap_seconds": PHASE15_MAX_QUOTE_AGE_SECONDS,
                    "snapshot_within_quote_age_cap": False,
                    "subscribed": False,
                    "realtime": False,
                    "delay_zero": False,
                    "no_open_transport_gap": False,
                    "regular_session": False,
                    "has_fresh_quote_within_age_cap": False,
                },
                "quotes": [],
                "reason": "LIVE_MARKET_STATE_UNAVAILABLE",
            }

        snapshot = LiveStateSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        snapshot_age_seconds = max(0.0, (now_utc - snapshot.generated_at_utc).total_seconds())
        snapshot_current = snapshot_age_seconds <= PHASE15_MAX_QUOTE_AGE_SECONDS
        quotes: list[dict[str, Any]] = []
        for symbol_state in snapshot.symbols:
            if symbol_state.quote is None:
                continue
            quote = symbol_state.quote
            provider_age_seconds = max(
                0.0, (now_utc - quote.provider_timestamp_utc).total_seconds()
            )
            quotes.append(
                {
                    "ticker": symbol_state.symbol,
                    "as_of_utc": symbol_state.as_of_utc.isoformat(),
                    "quote_freshness": symbol_state.quote_freshness.value,
                    "provider_timestamp_utc": quote.provider_timestamp_utc.isoformat(),
                    "provider_age_seconds": round(provider_age_seconds, 2),
                    "received_at_utc": quote.received_at_utc.isoformat(),
                    "session_date": quote.session_date.isoformat(),
                    "session_segment": quote.session_segment.value,
                    "bid_price": quote.bid_price,
                    "bid_size": quote.bid_size,
                    "ask_price": quote.ask_price,
                    "ask_size": quote.ask_size,
                    "feed_mode": quote.feed_mode.value,
                    "expected_delay_seconds": quote.expected_delay_seconds,
                }
            )
        quotes.sort(key=lambda row: str(row["ticker"]))
        fresh_quote_present = any(
            row["quote_freshness"] == LiveFreshness.FRESH.value
            and float(row["provider_age_seconds"]) <= PHASE15_MAX_QUOTE_AGE_SECONDS
            for row in quotes
        )
        subscribed = snapshot.connection_state == LiveConnectionState.SUBSCRIBED
        realtime = snapshot.feed_mode == LiveFeedMode.REALTIME
        delay_zero = snapshot.expected_delay_seconds == 0
        no_open_gap = snapshot.open_transport_gap_started_at_utc is None
        regular_session = snapshot.session.session_segment == SessionSegment.REGULAR
        inputs_ready = all(
            [
                snapshot_current,
                subscribed,
                realtime,
                delay_zero,
                no_open_gap,
                regular_session,
                fresh_quote_present,
            ]
        )
        return {
            "available": True,
            "generated_at_utc": snapshot.generated_at_utc.isoformat(),
            "snapshot_age_seconds": round(snapshot_age_seconds, 2),
            "feed_mode": snapshot.feed_mode.value,
            "expected_delay_seconds": snapshot.expected_delay_seconds,
            "connection_state": snapshot.connection_state.value,
            "subscriptions": list(snapshot.subscriptions),
            "session": {
                "as_of_utc": snapshot.session.as_of_utc.isoformat(),
                "local_date": snapshot.session.local_date.isoformat(),
                "is_exchange_session": snapshot.session.is_exchange_session,
                "session_segment": snapshot.session.session_segment.value,
                "regular_open_utc": snapshot.session.regular_open_utc.isoformat()
                if snapshot.session.regular_open_utc
                else None,
                "regular_close_utc": snapshot.session.regular_close_utc.isoformat()
                if snapshot.session.regular_close_utc
                else None,
                "next_session_date": snapshot.session.next_session_date.isoformat()
                if snapshot.session.next_session_date
                else None,
                "next_regular_open_utc": snapshot.session.next_regular_open_utc.isoformat()
                if snapshot.session.next_regular_open_utc
                else None,
            },
            "received_events": snapshot.received_events,
            "accepted_events": snapshot.accepted_events,
            "ignored_out_of_order_events": snapshot.ignored_out_of_order_events,
            "parse_errors": snapshot.parse_errors,
            "reconnects": snapshot.reconnects,
            "restored_symbol_count": snapshot.restored_symbol_count,
            "observed_symbol_count": snapshot.observed_symbol_count,
            "symbol_count": snapshot.symbol_count,
            "transport_gap_count": snapshot.transport_gap_count,
            "open_transport_gap": snapshot.open_transport_gap_started_at_utc is not None,
            "last_received_at_utc": snapshot.last_received_at_utc.isoformat()
            if snapshot.last_received_at_utc
            else None,
            "phase18_market_inputs": {
                "diagnostic_only": True,
                "state": "INPUTS_APPEAR_READY" if inputs_ready else "NOT_READY",
                "quote_age_cap_seconds": PHASE15_MAX_QUOTE_AGE_SECONDS,
                "snapshot_within_quote_age_cap": snapshot_current,
                "subscribed": subscribed,
                "realtime": realtime,
                "delay_zero": delay_zero,
                "no_open_transport_gap": no_open_gap,
                "regular_session": regular_session,
                "has_fresh_quote_within_age_cap": fresh_quote_present,
            },
            "quotes": quotes[:PHASE19_LIVE_QUOTE_LIMIT],
            "display_limit": PHASE19_LIVE_QUOTE_LIMIT,
            "reason": None,
        }

    def snapshot(self) -> dict[str, Any]:
        now_utc = self._now_utc()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        now_utc = now_utc.astimezone(UTC)

        system = self.status_service.system_status().model_dump(mode="json")
        candidates = self._candidate_summary(now_utc=now_utc)
        ai = self._ai_summary(now_utc=now_utc)
        outcomes = self._outcome_summary()
        live_market = self._live_market_summary(now_utc=now_utc)
        return {
            "contract_version": PHASE19_OBSERVABILITY_CONTRACT_VERSION,
            "generated_at_utc": now_utc.isoformat(),
            "phase": {
                "merge_authoritative_phase": "18B",
                "merge_authoritative_state": "WAITING_EXTERNAL",
                "stacked_phase": "19",
                "stacked_phase_name": "Operations Dashboard & Paper/Shadow Observability",
                "stacked_phase_state": "STACKED_PREP_GREEN",
            },
            "authority": {
                "mode": "READ_ONLY_LOCAL_ARTIFACT_OBSERVABILITY",
                "provider_reads": 0,
                "provider_writes": 0,
                "live_execution_promoted": False,
                "automatic_cross_broker_failover_allowed": False,
                "browser_execution_authority": False,
                "artifact_recency_diagnostic_only": True,
                "live_market_state_diagnostic_only": True,
                "phase19_policy_fingerprint": phase19_policy_fingerprint(),
            },
            "pipeline": {
                "live_market_state": {
                    "available": live_market["available"],
                    "connection_state": live_market["connection_state"],
                    "feed_mode": live_market["feed_mode"],
                    "session_segment": (live_market["session"] or {}).get("session_segment")
                    if isinstance(live_market.get("session"), dict)
                    else None,
                    "phase18_input_state": live_market["phase18_market_inputs"]["state"],
                },
                "candidate_materialization": {
                    "available": candidates["available"],
                    "as_of_date": candidates["as_of_date"],
                    "count": candidates["considered_count"],
                    "promoted": candidates["promoted_count"],
                    "age_hours": candidates["age_hours"],
                    "recency_state": candidates["recency_state"],
                },
                "ai_audit": {
                    "available": ai["available"],
                    "as_of_date": ai["as_of_date"],
                    "count": ai["review_count"],
                    "age_hours": ai["age_hours"],
                    "recency_state": ai["recency_state"],
                },
                "execution_outcomes": {
                    "available": outcomes["available"],
                    "count": outcomes["outcome_count"],
                    "latest_closed_at_utc": outcomes["latest_closed_at_utc"],
                },
            },
            "artifact_recency": {
                "recent_threshold_hours": PHASE19_RECENT_ARTIFACT_HOURS,
                "diagnostic_only": True,
                "candidate_materialization": {
                    "generated_at_utc": candidates["generated_at_utc"],
                    "age_hours": candidates["age_hours"],
                    "state": candidates["recency_state"],
                },
                "ai_audit": {
                    "generated_at_utc": ai["generated_at_utc"],
                    "age_hours": ai["age_hours"],
                    "state": ai["recency_state"],
                },
            },
            "system": system,
            "live_market": live_market,
            "candidates": candidates,
            "ai_audit": ai,
            "outcomes": outcomes,
            "policy": phase19_policy_payload(),
        }
