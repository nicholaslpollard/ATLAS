from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase32_finalist_audit import (
    PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
    PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
)
from .phase32_policy import (
    PHASE32_AUTOMATION_WRITES,
    PHASE32_AUTOMATIC_BROKER_FAILOVER,
    PHASE32_BROKER_READS,
    PHASE32_BROKER_WRITES,
    PHASE32_LIVE_WRITES,
    PHASE32_ORDER_WRITES,
    PHASE32_PAPER_SUBMITS,
    PHASE32_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    PHASE32_PROTECTED_MIN_EVENT_ROWS,
    PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
    PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_PROVIDER_WRITES,
    phase32_policy_fingerprint,
)

PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase32-closeout-v1-sec-8k-material-event-alpha-accepted-negative-protected-unread"
)

# Accepted target-machine finalist-audit evidence, 2026-08-30.
PHASE32_ACCEPTED_AUDIT_FINGERPRINT = (
    "c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e"
)
PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT = (
    "2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344"
)
PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256 = (
    "b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703"
)
PHASE32_ACCEPTED_AUDIT_STATUS = "AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE"
PHASE32_ACCEPTED_FINALIST_IDS = ("solvency_distress_short",)
PHASE32_ACCEPTED_SELECTION_SURVIVORS = (
    "equity_issuance_short",
    "financial_integrity_adverse_short",
    "listing_distress_short",
    "share_repurchase_long",
    "solvency_distress_short",
)
PHASE32_ACCEPTED_SELECTION_WINNERS = (
    "share_repurchase_long",
    "solvency_distress_short",
)
PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS = 46
PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS = 33
PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS = 40


class Phase32CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase32CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase32CloseoutError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase32CloseoutError(f"{label} must be a JSON object")
    return payload


def phase32_disposition_from_source_gate(*, event_rows: int, signal_sessions: int, unique_instruments: int) -> tuple[str, bool]:
    possible = (
        event_rows >= PHASE32_PROTECTED_MIN_EVENT_ROWS
        and signal_sessions >= PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS
        and unique_instruments >= PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS
    )
    if possible:
        return "PENDING_PROTECTED_CONFIRMATION", False
    return "ACCEPTED_NEGATIVE", False


def _all_zero(payload: Mapping[str, object], fields: tuple[str, ...]) -> bool:
    return all(int(payload.get(field, -1)) == 0 for field in fields)


class Phase32Closeout:
    """Close Phase32 negative from the frozen source-only protected sample impossibility proof.

    This class must never read protected stock/SPY returns. It only validates the already-created
    finalist audit and source-only protected-plan artifacts and records the phase disposition.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase32" / "v1"
        self.audit_root = self.root / "finalist_audit"

    def audit_path(self) -> Path:
        return self.audit_root / "finalist_blindness_audit.json"

    def protected_plan_path(self) -> Path:
        return self.audit_root / "protected_plan.json"

    def protected_plan_rows_path(self) -> Path:
        return self.audit_root / "protected_plan_rows.jsonl"

    def report_path(self) -> Path:
        return self.root / "phase32_closeout_report.json"

    def run(self) -> dict[str, Any]:
        audit = _read_json(self.audit_path(), "Phase32 finalist blindness audit")
        plan = _read_json(self.protected_plan_path(), "Phase32 protected source-only plan")

        source_gate = audit.get("protected_source_only_sample_gate")
        plan_gate = plan.get("source_only_sample_gate")
        if not isinstance(source_gate, Mapping) or not isinstance(plan_gate, Mapping):
            raise Phase32CloseoutError("Phase32 source-only sample-gate evidence is missing")
        checks = source_gate.get("checks")
        plan_checks = plan_gate.get("checks")
        if not isinstance(checks, Mapping) or not isinstance(plan_checks, Mapping):
            raise Phase32CloseoutError("Phase32 source-only sample-gate checks are missing")

        event_rows = int(source_gate.get("event_rows", -1))
        signal_sessions = int(source_gate.get("signal_sessions", -1))
        unique_instruments = int(source_gate.get("unique_instruments", -1))
        disposition, phase33_entry_satisfied = phase32_disposition_from_source_gate(
            event_rows=event_rows,
            signal_sessions=signal_sessions,
            unique_instruments=unique_instruments,
        )
        if disposition != "ACCEPTED_NEGATIVE":
            raise Phase32CloseoutError(
                "Phase32 negative closeout is forbidden when the frozen protected source population can satisfy 50/20/20"
            )

        activity_fields = (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "automation_writes",
        )
        forbidden_protected_artifacts = (
            self.root / "protected_confirmation",
            self.root / "protected_evaluation",
            self.root / "protected_outcomes.parquet",
            self.root / "protected_returns.parquet",
        )

        closeout_checks = {
            "policy_fingerprint_exact": audit.get("phase32_policy_fingerprint") == phase32_policy_fingerprint()
            and plan.get("phase32_policy_fingerprint") == phase32_policy_fingerprint(),
            "audit_contract_exact": audit.get("contract_version")
            == PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "protected_plan_contract_exact": plan.get("contract_version")
            == PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
            "audit_pass": audit.get("pass") is True,
            "audit_status_exact": audit.get("status") == PHASE32_ACCEPTED_AUDIT_STATUS,
            "audit_fingerprint_exact": audit.get("audit_fingerprint") == PHASE32_ACCEPTED_AUDIT_FINGERPRINT,
            "protected_plan_fingerprint_exact": audit.get("protected_plan_fingerprint")
            == PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT
            and plan.get("plan_fingerprint") == PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT,
            "protected_plan_rows_sha_exact": audit.get("protected_plan_rows_sha256")
            == PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256
            and plan.get("protected_plan_rows_sha256") == PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256
            and self.protected_plan_rows_path().is_file()
            and sha256_file(self.protected_plan_rows_path()) == PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256,
            "selection_survivors_exact": tuple(audit.get("selection_survivor_ids") or [])
            == PHASE32_ACCEPTED_SELECTION_SURVIVORS,
            "selection_winners_exact": tuple(audit.get("selection_winner_ids") or [])
            == PHASE32_ACCEPTED_SELECTION_WINNERS,
            "finalist_exact": tuple(audit.get("finalist_ids") or []) == PHASE32_ACCEPTED_FINALIST_IDS
            and tuple(plan.get("finalist_ids") or []) == PHASE32_ACCEPTED_FINALIST_IDS,
            "source_counts_exact": event_rows == PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS
            and signal_sessions == PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS
            and unique_instruments == PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS
            and int(plan_gate.get("event_rows", -1)) == PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS
            and int(plan_gate.get("signal_sessions", -1)) == PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS
            and int(plan_gate.get("unique_instruments", -1)) == PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS,
            "event_row_gate_failed_only": checks.get("min_event_rows") is False
            and checks.get("min_signal_sessions") is True
            and checks.get("min_unique_instruments") is True
            and plan_checks == checks,
            "source_gate_impossible": source_gate.get("possible") is False and plan_gate.get("possible") is False,
            "protected_return_not_authorized": audit.get("protected_return_authorized_after_fingerprint_freeze") is False,
            "protected_returns_unread": int(audit.get("protected_return_rows_read", -1)) == 0
            and int(plan.get("protected_return_rows_read", -1)) == 0,
            "protected_holdout_unconsumed": audit.get("protected_holdout_consumed") is False
            and plan.get("protected_holdout_consumed") is False,
            "activity_zero": _all_zero(audit, activity_fields) and _all_zero(plan, activity_fields),
            "no_protected_performance_artifacts": not any(path.exists() for path in forbidden_protected_artifacts),
            "policy_external_authority_zero": all(
                value == 0
                for value in (
                    PHASE32_PROVIDER_WRITES,
                    PHASE32_BROKER_READS,
                    PHASE32_BROKER_WRITES,
                    PHASE32_ORDER_WRITES,
                    PHASE32_PAPER_SUBMITS,
                    PHASE32_LIVE_WRITES,
                    PHASE32_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": PHASE32_AUTOMATIC_BROKER_FAILOVER is False,
            "phase33_authority_blocked": PHASE32_PHASE33_SIGNAL_TO_TRADE_AUTHORITY is False
            and phase33_entry_satisfied is False,
        }
        if not all(closeout_checks.values()):
            failed = sorted(name for name, passed in closeout_checks.items() if not passed)
            raise Phase32CloseoutError("Phase32 negative closeout failed: " + ", ".join(failed))

        report: dict[str, Any] = {
            "contract_version": PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase32_policy_fingerprint": phase32_policy_fingerprint(),
            "phase32_disposition": disposition,
            "phase33_entry_satisfied": phase33_entry_satisfied,
            "historical_supported_alpha_count_after_phase32": 0,
            "selection_survivor_ids": list(PHASE32_ACCEPTED_SELECTION_SURVIVORS),
            "selection_winner_ids": list(PHASE32_ACCEPTED_SELECTION_WINNERS),
            "development_finalist_ids": list(PHASE32_ACCEPTED_FINALIST_IDS),
            "supported_candidate_ids": [],
            "protected_source_only_event_rows": event_rows,
            "protected_source_only_signal_sessions": signal_sessions,
            "protected_source_only_unique_instruments": unique_instruments,
            "protected_min_event_rows": PHASE32_PROTECTED_MIN_EVENT_ROWS,
            "protected_min_signal_sessions": PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
            "protected_min_unique_instruments": PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
            "failed_protected_source_gate": "min_event_rows",
            "finalist_audit_fingerprint": PHASE32_ACCEPTED_AUDIT_FINGERPRINT,
            "protected_plan_fingerprint": PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT,
            "protected_plan_rows_sha256": PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": closeout_checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(self.report_path().resolve()),
            "pass": True,
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
