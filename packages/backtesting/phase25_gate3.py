from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.features.partition_store import sha256_file
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION

from .phase25_gate2 import (
    PHASE25_GATE2_REPORT_CONTRACT_VERSION,
    Phase25Gate2ActiveOnlyEquivalence,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_GATE3_ACTIVE,
    PHASE25_GATE3_ATOMIC_SESSION_PERSISTENCE_REQUIRED,
    PHASE25_GATE3_CONTRACT_VERSION,
    PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED,
    PHASE25_GATE3_ENDPOINT,
    PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED,
    PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE,
    PHASE25_GATE3_INCLUDE_INACTIVE,
    PHASE25_GATE3_MARKET,
    PHASE25_GATE3_ORDER,
    PHASE25_GATE3_PAGE_LIMIT,
    PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_GATE3_PROVIDER_NATIVE_TICKER_CASE_PRESERVED,
    PHASE25_GATE3_RESUME_FROM_VALIDATED_PAIRS_ONLY,
    PHASE25_GATE3_SORT,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
)


PHASE25_GATE3_REPORT_CONTRACT_VERSION = (
    "phase25-gate3-report-v1-active-only-exact-pit-acquisition-plan"
)


class Phase25Gate3Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReferencePairState:
    session_date: str
    snapshot_exists: bool
    manifest_exists: bool
    valid_pair: bool
    include_inactive: bool | None
    action: str


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate3Error(f"missing required JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate3Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate3Error(f"JSON evidence must be an object: {path}")
    return payload


def observed_page_bounds(active_row_counts: list[int], *, page_limit: int) -> tuple[int, int]:
    if page_limit <= 0:
        raise ValueError("page_limit must be positive")
    if not active_row_counts or any(value <= 0 for value in active_row_counts):
        raise ValueError("active_row_counts must contain only positive values")
    pages = [math.ceil(value / page_limit) for value in active_row_counts]
    return min(pages), max(pages)


def projected_request_bounds(
    *, missing_sessions: int,
    observed_min_pages: int,
    observed_max_pages: int,
) -> tuple[int, int]:
    if missing_sessions < 0:
        raise ValueError("missing_sessions cannot be negative")
    if observed_min_pages <= 0 or observed_max_pages < observed_min_pages:
        raise ValueError("invalid observed page bounds")
    return missing_sessions * observed_min_pages, missing_sessions * observed_max_pages


class Phase25Gate3AcquisitionPlan:
    """Provider-free preregistration of the exact active-only PIT acquisition scope."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate3"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "active_only_acquisition_plan.json"

    def _gate2_evidence(self, through_date: date) -> tuple[Path, dict[str, object]]:
        path = Phase25Gate2ActiveOnlyEquivalence(self.settings).report_path(through_date)
        report = _read_json(path)
        if report.get("contract_version") != PHASE25_GATE2_REPORT_CONTRACT_VERSION:
            raise Phase25Gate3Error("Gate2 report contract mismatch")
        if report.get("through_date") != through_date.isoformat():
            raise Phase25Gate3Error("Gate2 report through-date mismatch")
        if report.get("phase25_gate2_policy_fingerprint") != phase25_gate2_policy_fingerprint():
            raise Phase25Gate3Error("Gate2 policy fingerprint mismatch")
        if report.get("pass") is not True or report.get("all_dates_equivalent") is not True:
            raise Phase25Gate3Error("Gate2 active-only equivalence evidence is not passing")
        if report.get("recommendation") != "GATE3_PREREGISTER_ACTIVE_ONLY_EXACT_PIT_ACQUISITION":
            raise Phase25Gate3Error("Gate2 recommendation does not authorize Gate3 preregistration")
        for key in (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "phase11_support_writes",
            "protected_strategy_evidence_reads",
        ):
            if int(report.get(key, -1)) != 0:
                raise Phase25Gate3Error(f"Gate2 authority counter is nonzero: {key}")
        return path, report

    def _reference_pair_state(self, session: date) -> ReferencePairState:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest_path = self.paths.reference_snapshot_manifest(session)
        snapshot_exists = snapshot.is_file()
        manifest_exists = manifest_path.is_file()
        if snapshot_exists != manifest_exists:
            raise Phase25Gate3Error(
                f"partial reference state requires manual reconciliation before acquisition: {session}"
            )
        if not snapshot_exists:
            return ReferencePairState(
                session_date=session.isoformat(),
                snapshot_exists=False,
                manifest_exists=False,
                valid_pair=False,
                include_inactive=None,
                action="ACQUIRE_ACTIVE_ONLY_EXACT_PIT",
            )

        manifest = _read_json(manifest_path)
        if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
            raise Phase25Gate3Error(f"reference contract mismatch: {session}")
        if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
            raise Phase25Gate3Error(f"reference identity contract mismatch: {session}")
        if manifest.get("as_of_date") != session.isoformat():
            raise Phase25Gate3Error(f"reference manifest as_of_date mismatch: {session}")
        include_inactive = manifest.get("include_inactive")
        if not isinstance(include_inactive, bool):
            raise Phase25Gate3Error(f"reference manifest include_inactive is not boolean: {session}")
        if int(manifest.get("row_count", 0)) <= 0 or int(manifest.get("instrument_count", 0)) <= 0:
            raise Phase25Gate3Error(f"reference manifest contains nonpositive counts: {session}")
        return ReferencePairState(
            session_date=session.isoformat(),
            snapshot_exists=True,
            manifest_exists=True,
            valid_pair=True,
            include_inactive=include_inactive,
            action="PRESERVE_EXISTING_VALID_REFERENCE",
        )

    def run(self, *, through_date: date) -> dict[str, object]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate3Error("through_date predates the locked Phase25 replay origin")
        if not self.calendar.is_session(through_date):
            raise Phase25Gate3Error(f"through_date is not an exchange session: {through_date}")

        gate2_path, gate2 = self._gate2_evidence(through_date)
        sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date))
        if not sessions or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate3Error("Gate3 session enumeration does not begin at the locked replay origin")

        states = tuple(self._reference_pair_state(session) for session in sessions)
        existing = tuple(item for item in states if item.valid_pair)
        missing = tuple(item for item in states if not item.valid_pair)
        acquisition_sessions = tuple(date.fromisoformat(item.session_date) for item in missing)

        tested = gate2.get("date_equivalence")
        if not isinstance(tested, list) or not tested:
            raise Phase25Gate3Error("Gate2 does not contain per-date equivalence evidence")
        active_rows: list[int] = []
        for item in tested:
            if not isinstance(item, dict):
                raise Phase25Gate3Error("Gate2 date equivalence row is malformed")
            active_rows.append(int(item.get("active_reference_rows", 0)))
        observed_min_pages, observed_max_pages = observed_page_bounds(
            active_rows,
            page_limit=PHASE25_GATE3_PAGE_LIMIT,
        )
        projected_min_requests, projected_max_requests = projected_request_bounds(
            missing_sessions=len(missing),
            observed_min_pages=observed_min_pages,
            observed_max_pages=observed_max_pages,
        )

        existing_full = sum(item.include_inactive is True for item in existing)
        existing_active_only = sum(item.include_inactive is False for item in existing)
        entitlement_probe_session = acquisition_sessions[0] if acquisition_sessions else None
        acquisition_required = bool(acquisition_sessions)
        recommendation = (
            "GATE4_IMPLEMENT_EXPLICIT_RUN_SCOPED_ACTIVE_ONLY_MASSIVE_READ_AUTHORITY"
            if acquisition_required
            else "GATE4_SKIP_ACQUISITION_AND_RECONSTRUCT_PIT_UNIVERSE"
        )

        gate2_sha = sha256_file(gate2_path)
        source_payload: dict[str, Any] = {
            "gate2_report_sha256": gate2_sha,
            "sessions": [item.isoformat() for item in sessions],
            "existing_reference_sessions": [item.session_date for item in existing],
            "acquisition_sessions": [item.session_date for item in missing],
            "acquisition_query": {
                "method": "GET",
                "endpoint": PHASE25_GATE3_ENDPOINT,
                "market": PHASE25_GATE3_MARKET,
                "active": PHASE25_GATE3_ACTIVE,
                "order": PHASE25_GATE3_ORDER,
                "sort": PHASE25_GATE3_SORT,
                "limit": PHASE25_GATE3_PAGE_LIMIT,
                "date": "EXACT_SESSION_DATE",
            },
        }
        source_fingerprint = hashlib.sha256(
            json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE3_REPORT_CONTRACT_VERSION,
            "gate3_policy_contract_version": PHASE25_GATE3_CONTRACT_VERSION,
            "phase25_gate3_policy_fingerprint": phase25_gate3_policy_fingerprint(),
            "phase25_gate2_policy_fingerprint": phase25_gate2_policy_fingerprint(),
            "gate2_report_contract_version": PHASE25_GATE2_REPORT_CONTRACT_VERSION,
            "gate2_report_path": str(gate2_path.resolve()),
            "gate2_report_sha256": gate2_sha,
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "through_date": through_date.isoformat(),
            "replay_session_count": len(sessions),
            "existing_valid_reference_session_count": len(existing),
            "existing_full_reference_session_count": existing_full,
            "existing_active_only_reference_session_count": existing_active_only,
            "acquisition_session_count": len(missing),
            "existing_reference_sessions": [item.session_date for item in existing],
            "acquisition_sessions": [item.session_date for item in missing],
            "entitlement_probe_session": entitlement_probe_session.isoformat() if entitlement_probe_session else None,
            "reference_pair_state": [asdict(item) for item in states],
            "acquisition_query": {
                "method": "GET",
                "endpoint": PHASE25_GATE3_ENDPOINT,
                "market": PHASE25_GATE3_MARKET,
                "active": PHASE25_GATE3_ACTIVE,
                "order": PHASE25_GATE3_ORDER,
                "sort": PHASE25_GATE3_SORT,
                "limit": PHASE25_GATE3_PAGE_LIMIT,
                "date": "EXACT_SESSION_DATE",
                "include_inactive": PHASE25_GATE3_INCLUDE_INACTIVE,
                "pagination": "FOLLOW_SAME_HOST_NEXT_URL_UNTIL_ABSENT",
            },
            "observed_active_rows_per_tested_session": active_rows,
            "observed_pages_per_session_min": observed_min_pages,
            "observed_pages_per_session_max": observed_max_pages,
            "projected_provider_page_requests_min": projected_min_requests,
            "projected_provider_page_requests_max": projected_max_requests,
            "projected_request_estimate_is_authority": False,
            "gate4_execution_requirements": {
                "separate_explicit_run_scoped_read_authority": True,
                "earliest_missing_session_entitlement_probe_first": PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED,
                "abort_bulk_acquisition_if_entitlement_probe_fails": True,
                "preserve_existing_valid_reference_pairs": PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED,
                "force_replace_existing_reference": PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE,
                "provider_native_ticker_case_preserved": PHASE25_GATE3_PROVIDER_NATIVE_TICKER_CASE_PRESERVED,
                "atomic_per_session_persistence": PHASE25_GATE3_ATOMIC_SESSION_PERSISTENCE_REQUIRED,
                "resume_only_from_validated_reference_pairs": PHASE25_GATE3_RESUME_FROM_VALIDATED_PAIRS_ONLY,
                "new_manifest_include_inactive": PHASE25_GATE3_INCLUDE_INACTIVE,
                "new_snapshot_requires_positive_rows": True,
                "new_snapshot_requires_all_rows_active": True,
                "new_manifest_requires_exact_session_date": True,
                "no_strategy_return_reads": True,
                "no_protected_strategy_evidence_reads": True,
                "no_broker_order_paper_live_authority": True,
                "no_phase11_support_writes": True,
                "no_blind_retry_after_unreconciled_partial_session": True,
            },
            "source_fingerprint": source_fingerprint,
            "active_only_reference_acquisition_authority": PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
            "recommendation": recommendation,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "provider_reads": PHASE25_PROVIDER_READS,
            "provider_writes": PHASE25_PROVIDER_WRITES,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "checks": {
                "gate2_equivalence_passing": True,
                "provider_acquisition_authority_forbidden": PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False,
                "exact_active_only_query_locked": PHASE25_GATE3_ENDPOINT == "/v3/reference/tickers" and PHASE25_GATE3_MARKET == "stocks" and PHASE25_GATE3_ACTIVE is True,
                "existing_valid_reference_preserved": PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED is True,
                "force_replace_existing_reference_forbidden": PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE is False,
                "entitlement_probe_required": PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED is True,
                "provider_reads_zero": PHASE25_PROVIDER_READS == 0,
                "provider_writes_zero": PHASE25_PROVIDER_WRITES == 0,
                "broker_reads_writes_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0,
                "order_paper_live_writes_zero": PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
                "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
                "protected_strategy_evidence_reads_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
            },
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
