from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.enums import LiveFreshness
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.schemas.execution import ExecutionOutcome
from packages.schemas.execution_attempt import ExecutionAttemptRecord
from packages.schemas.live_market import LiveStateSnapshot


PAPER_DASHBOARD_CONTRACT_VERSION = (
    "a34.5-paper-dashboard-v1-local-authoritative-artifacts-no-provider-calls"
)
PAPER_DASHBOARD_RECORD_LIMIT = 50


class PaperDashboardError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PaperDashboardError(f"JSON root must be an object: {path}")
    return payload


def _latest_manifest(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    paths = sorted(path for path in root.rglob("*.json") if path.is_file())
    return paths[-1] if paths else None


def _public_account(attempt: ExecutionAttemptRecord) -> dict[str, Any]:
    account = attempt.reconciliation_before.account
    return {
        "broker": account.broker.value,
        "environment": account.environment.value,
        "as_of_utc": account.as_of_utc.isoformat(),
        "equity": account.equity,
        "cash": account.cash,
        "buying_power": account.buying_power,
        "gross_market_value": account.gross_market_value,
        "trading_blocked": account.trading_blocked,
        "shorting_enabled": account.shorting_enabled,
        "snapshot_kind": "LAST_RECONCILED_PRE_SUBMIT",
    }


def _public_reconciled_positions(attempt: ExecutionAttemptRecord) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in attempt.reconciliation_before.positions:
        rows.append(
            {
                "ticker": item.ticker,
                "quantity": item.quantity,
                "market_value": item.market_value,
                "average_entry_price": item.average_entry_price,
                "as_of_utc": item.as_of_utc.isoformat(),
            }
        )
    return rows


def _public_outcome(outcome: ExecutionOutcome) -> dict[str, Any]:
    return {
        "intent_id": outcome.intent_id,
        "broker": outcome.broker.value,
        "environment": outcome.environment.value,
        "ticker": outcome.ticker,
        "direction": outcome.direction.value,
        "quantity": outcome.quantity,
        "entry_fill_price": outcome.entry_fill_price,
        "exit_fill_price": outcome.exit_fill_price,
        "opened_at_utc": outcome.opened_at_utc.isoformat(),
        "closed_at_utc": outcome.closed_at_utc.isoformat(),
        "exit_reason": outcome.exit_reason.value,
        "gross_pnl": outcome.gross_pnl,
        "gross_return": outcome.gross_return,
        "realized_r": outcome.realized_r,
        "pnl_basis": "PHASE15_REALIZED_GROSS_DESCRIPTIVE_ONLY",
    }


class PaperDashboardService:
    """Read-only A34.5 operator view over accepted local execution evidence.

    This service never initializes a broker or provider. It verifies Phase15 artifact
    hashes and schemas, reads the persisted Phase5 live-state file only, and exposes
    sanitized operator state. Browser refresh therefore cannot submit, retry, cancel,
    reconcile through a network, or otherwise mutate trading state.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.derived = settings.resolved_path(settings.data.paths.derived)
        self.phase15_root = self.derived / "execution" / "phase15" / "v1"
        self.market_paths = MarketDataPaths(settings)
        self._now_utc = now_utc or (lambda: datetime.now(UTC))

    def _safe_artifact(self, raw_path: Any, expected_sha: Any) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise PaperDashboardError("execution artifact path is missing")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise PaperDashboardError("execution artifact hash is missing")
        path = Path(raw_path).resolve()
        root = self.phase15_root.resolve()
        if not path.is_relative_to(root):
            raise PaperDashboardError("execution artifact escaped Phase15 root")
        if not path.is_file():
            raise PaperDashboardError(f"execution artifact is unavailable: {path.name}")
        if _sha256(path) != expected_sha:
            raise PaperDashboardError(f"execution artifact hash mismatch: {path.name}")
        return path

    def _attempts(self, manifest: dict[str, Any]) -> tuple[list[ExecutionAttemptRecord], list[dict[str, Any]]]:
        attempts: list[ExecutionAttemptRecord] = []
        decisions: list[dict[str, Any]] = []
        records = manifest.get("records")
        if not isinstance(records, list):
            raise PaperDashboardError("Phase15 manifest records are invalid")
        for row in records:
            if not isinstance(row, dict):
                raise PaperDashboardError("Phase15 manifest record is invalid")
            decisions.append(
                {
                    "ticker": row.get("ticker"),
                    "as_of_date": row.get("as_of_date"),
                    "environment": row.get("environment"),
                    "broker": row.get("broker"),
                    "disposition": row.get("disposition"),
                    "reason_codes": row.get("reason_codes") or [],
                    "provider_submission_attempted": bool(row.get("provider_submission_attempted")),
                    "provider_submission_uncertain": bool(row.get("provider_submission_uncertain")),
                }
            )
            if not row.get("attempt_path"):
                continue
            attempt_path = self._safe_artifact(row.get("attempt_path"), row.get("attempt_sha256"))
            attempts.append(ExecutionAttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8")))
        attempts.sort(key=lambda item: item.attempted_at_utc, reverse=True)
        decisions.reverse()
        return attempts, decisions[:PAPER_DASHBOARD_RECORD_LIMIT]

    def _outcomes(self) -> list[ExecutionOutcome]:
        root = self.phase15_root / "outcomes"
        if not root.is_dir():
            return []
        outcomes = [
            ExecutionOutcome.model_validate_json(path.read_text(encoding="utf-8"))
            for path in root.rglob("outcome.json")
            if path.is_file()
        ]
        outcomes.sort(key=lambda item: item.closed_at_utc, reverse=True)
        return outcomes

    def _fresh_marks(self, now_utc: datetime) -> dict[str, dict[str, Any]]:
        path = self.market_paths.live_state_file()
        if not path.is_file():
            return {}
        snapshot = LiveStateSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        marks: dict[str, dict[str, Any]] = {}
        for state in snapshot.symbols:
            quote = state.quote
            if quote is None or state.quote_freshness != LiveFreshness.FRESH:
                continue
            age = max(0.0, (now_utc - quote.provider_timestamp_utc).total_seconds())
            if age > PHASE15_MAX_QUOTE_AGE_SECONDS:
                continue
            marks[state.symbol] = {
                "bid": quote.bid_price,
                "ask": quote.ask_price,
                "provider_timestamp_utc": quote.provider_timestamp_utc.isoformat(),
                "received_at_utc": quote.received_at_utc.isoformat(),
                "age_seconds": round(age, 2),
                "session_segment": quote.session_segment.value,
                "feed_mode": quote.feed_mode.value,
            }
        return marks

    def _open_positions(
        self,
        attempts: list[ExecutionAttemptRecord],
        closed_intent_ids: set[str],
        marks: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for attempt in attempts:
            intent = attempt.intent
            order = attempt.order_snapshot
            if intent.intent_id in seen or intent.intent_id in closed_intent_ids:
                continue
            seen.add(intent.intent_id)
            if order.filled_quantity <= 0 or order.average_fill_price is None:
                continue
            mark = marks.get(intent.ticker)
            mark_price: float | None = None
            unrealized_pnl: float | None = None
            unrealized_return: float | None = None
            if mark is not None:
                if intent.direction.value == "BULLISH":
                    mark_price = float(mark["bid"])
                    delta = mark_price - order.average_fill_price
                else:
                    mark_price = float(mark["ask"])
                    delta = order.average_fill_price - mark_price
                unrealized_pnl = delta * order.filled_quantity
                unrealized_return = delta / order.average_fill_price
            rows.append(
                {
                    "intent_id": intent.intent_id,
                    "ticker": intent.ticker,
                    "direction": intent.direction.value,
                    "side": order.side.value,
                    "quantity": order.filled_quantity,
                    "entry_price": order.average_fill_price,
                    "current_mark": mark_price,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_return": unrealized_return,
                    "mark_state": "FRESH_PERSISTED_QUOTE" if mark_price is not None else "UNAVAILABLE",
                    "mark_as_of_utc": mark.get("provider_timestamp_utc") if mark else None,
                    "stop": intent.stop,
                    "target": intent.target,
                    "proposed_loss_at_stop": attempt.risk_revalidation.proposed_loss_at_stop,
                    "submitted_at_utc": order.submitted_at_utc.isoformat() if order.submitted_at_utc else None,
                    "updated_at_utc": order.updated_at_utc.isoformat(),
                    "order_status": order.status.value,
                    "strategy_id": None,
                    "strategy_provenance": "UNAVAILABLE_UPSTREAM_STRATEGY_NOT_BOUND_TO_PHASE15_INTENT",
                    "decision_reason_codes": list(intent.reason_codes),
                    "risk_reason_codes": list(attempt.risk_revalidation.reason_codes),
                    "reconciliation_state": "ENTRY_EVIDENCE_PRESENT_RECONCILIATION_AFTER_ENTRY_NOT_IMPLIED",
                }
            )
        return rows[:PAPER_DASHBOARD_RECORD_LIMIT]

    @staticmethod
    def _orders(attempts: list[ExecutionAttemptRecord]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for attempt in attempts[:PAPER_DASHBOARD_RECORD_LIMIT]:
            item = attempt.order_snapshot
            rows.append(
                {
                    "intent_id": attempt.intent.intent_id,
                    "ticker": item.ticker,
                    "broker": item.broker.value,
                    "client_order_id": item.client_order_id,
                    "side": item.side.value,
                    "status": item.status.value,
                    "requested_quantity": item.requested_quantity,
                    "filled_quantity": item.filled_quantity,
                    "average_fill_price": item.average_fill_price,
                    "submitted_at_utc": item.submitted_at_utc.isoformat() if item.submitted_at_utc else None,
                    "updated_at_utc": item.updated_at_utc.isoformat(),
                    "existing_order_reused": attempt.existing_order_reused,
                    "provider_submission_performed": attempt.provider_submission_performed,
                }
            )
        return rows

    def snapshot(self) -> dict[str, Any]:
        now_utc = self._now_utc()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        now_utc = now_utc.astimezone(UTC)
        manifest_path = _latest_manifest(self.phase15_root / "manifests")
        if manifest_path is None:
            return {
                "contract_version": PAPER_DASHBOARD_CONTRACT_VERSION,
                "generated_at_utc": now_utc.isoformat(),
                "status": "NOT_RUN",
                "read_only": True,
                "provider_reads": 0,
                "provider_writes": 0,
                "broker_writes": 0,
                "account": None,
                "reconciled_positions": [],
                "open_positions": [],
                "decisions": [],
                "orders": [],
                "closed_trades": [],
                "statistics": {"closed_trade_count": 0, "total_realized_gross_pnl": 0.0},
                "health": {"reason": "PHASE15_EXECUTION_MANIFEST_UNAVAILABLE"},
            }
        try:
            manifest = _json(manifest_path)
            attempts, decisions = self._attempts(manifest)
            outcomes = self._outcomes()
            marks = self._fresh_marks(now_utc)
        except Exception as exc:
            return {
                "contract_version": PAPER_DASHBOARD_CONTRACT_VERSION,
                "generated_at_utc": now_utc.isoformat(),
                "status": "INVALID",
                "read_only": True,
                "provider_reads": 0,
                "provider_writes": 0,
                "broker_writes": 0,
                "error": type(exc).__name__,
                "account": None,
                "reconciled_positions": [],
                "open_positions": [],
                "decisions": [],
                "orders": [],
                "closed_trades": [],
                "statistics": {"closed_trade_count": 0, "total_realized_gross_pnl": 0.0},
                "health": {"reason": "LOCAL_EXECUTION_EVIDENCE_FAILED_VALIDATION"},
            }

        closed_intent_ids = {item.intent_id for item in outcomes}
        account_attempt = max(
            attempts,
            key=lambda item: item.reconciliation_before.account.as_of_utc,
            default=None,
        )
        closed_rows = [_public_outcome(item) for item in outcomes[:PAPER_DASHBOARD_RECORD_LIMIT]]
        total_realized = sum(item.gross_pnl for item in outcomes)
        provider_uncertain = int(manifest.get("provider_uncertain_count") or 0)
        requires_reconciliation = bool(manifest.get("requires_reconciliation"))
        status = "DEGRADED" if provider_uncertain or requires_reconciliation else "AVAILABLE"
        return {
            "contract_version": PAPER_DASHBOARD_CONTRACT_VERSION,
            "generated_at_utc": now_utc.isoformat(),
            "status": status,
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_writes": 0,
            "manifest": {
                "as_of_date": manifest.get("as_of_date"),
                "generated_at_utc": manifest.get("generated_at_utc"),
                "selected_environment": manifest.get("selected_environment"),
                "selected_broker": manifest.get("selected_broker"),
                "record_count": manifest.get("record_count"),
                "blocked_count": manifest.get("blocked_count"),
                "paper_submitted_count": manifest.get("paper_submitted_count"),
                "existing_reconciled_count": manifest.get("existing_reconciled_count"),
                "provider_uncertain_count": provider_uncertain,
                "requires_reconciliation": requires_reconciliation,
                "pass": manifest.get("pass"),
            },
            "account": _public_account(account_attempt) if account_attempt else None,
            "reconciled_positions": _public_reconciled_positions(account_attempt) if account_attempt else [],
            "open_positions": self._open_positions(attempts, closed_intent_ids, marks),
            "decisions": decisions,
            "orders": self._orders(attempts),
            "closed_trades": closed_rows,
            "statistics": {
                "closed_trade_count": len(outcomes),
                "total_realized_gross_pnl": total_realized,
                "winning_trade_count": sum(1 for item in outcomes if item.gross_pnl > 0),
                "losing_trade_count": sum(1 for item in outcomes if item.gross_pnl < 0),
                "net_realized_pnl": None,
                "net_realized_pnl_state": "UNAVAILABLE_PHASE15_OUTCOME_SCHEMA_IS_GROSS_ONLY",
            },
            "health": {
                "local_evidence_valid": True,
                "provider_submission_uncertain": provider_uncertain > 0,
                "requires_reconciliation": requires_reconciliation,
                "fresh_mark_count": len(marks),
                "automatic_broker_refresh": False,
                "browser_mutation_authority": False,
                "live_execution_promoted": False,
            },
        }
