from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION, InstrumentRegistryStore
from packages.providers.massive.reference_data import MassiveReferenceProvider

from .phase25_gate5 import (
    Phase25Gate5BulkAcquisition,
    _CountingMassiveRESTClient,
)
from .phase25_policy import PHASE25_ROUTE_REPLAY_ORIGIN


PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION = (
    "phase25-prerequisite-recovery-v1-authoritative-massive-pit"
)
PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION = (
    "phase25-prerequisite-recovery-validation-v1-exact-session-lineage"
)
PHASE25_PREREQUISITE_RECOVERY_PROVIDER = "massive"
PHASE25_PREREQUISITE_RECOVERY_READ_CLASS = (
    "MASSIVE_ACTIVE_ONLY_EXACT_PIT_REFERENCE_RECOVERY"
)


class Phase25PrerequisiteRecoveryError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25PrerequisiteRecoveryError(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25PrerequisiteRecoveryError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25PrerequisiteRecoveryError(f"JSON evidence must be an object: {path}")
    return value


def _validate_reference_pair_independently(
    paths: MarketDataPaths,
    session: date,
) -> dict[str, object]:
    snapshot = paths.reference_snapshot_file(session)
    manifest_path = paths.reference_snapshot_manifest(session)
    if not snapshot.is_file() or not manifest_path.is_file():
        raise Phase25PrerequisiteRecoveryError(f"reference pair is incomplete: {session}")

    manifest = _read_json(manifest_path)
    if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
        raise Phase25PrerequisiteRecoveryError(f"reference contract mismatch: {session}")
    if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
        raise Phase25PrerequisiteRecoveryError(f"reference identity contract mismatch: {session}")
    if manifest.get("as_of_date") != session.isoformat():
        raise Phase25PrerequisiteRecoveryError(f"reference manifest date mismatch: {session}")
    if manifest.get("include_inactive") is not False:
        raise Phase25PrerequisiteRecoveryError(
            f"reference pair is not active-only: {session}"
        )

    con = connect_utc(":memory:")
    try:
        row = con.execute(
            f"""
            SELECT
                count(*),
                count(DISTINCT instrument_id),
                count(*) FILTER (WHERE active = false OR active IS NULL),
                count(*) FILTER (WHERE trim(ticker) = ''),
                count(DISTINCT as_of_date),
                min(as_of_date),
                max(as_of_date)
            FROM read_parquet({sql_string(snapshot)})
            """
        ).fetchone()
    finally:
        con.close()

    rows = int(row[0])
    instruments = int(row[1])
    if rows <= 0 or instruments <= 0:
        raise Phase25PrerequisiteRecoveryError(
            f"reference pair has nonpositive counts: {session}"
        )
    if int(row[2]) != 0 or int(row[3]) != 0:
        raise Phase25PrerequisiteRecoveryError(
            f"reference pair contains inactive/blank-ticker rows: {session}"
        )
    if (
        int(row[4]) != 1
        or str(row[5]) != session.isoformat()
        or str(row[6]) != session.isoformat()
    ):
        raise Phase25PrerequisiteRecoveryError(
            f"reference snapshot session mismatch: {session}"
        )
    if int(manifest.get("row_count", -1)) != rows:
        raise Phase25PrerequisiteRecoveryError(
            f"reference manifest row-count mismatch: {session}"
        )
    if int(manifest.get("instrument_count", -1)) != instruments:
        raise Phase25PrerequisiteRecoveryError(
            f"reference manifest instrument-count mismatch: {session}"
        )
    return {
        "session": session.isoformat(),
        "row_count": rows,
        "instrument_count": instruments,
        "snapshot_sha256": sha256_file(snapshot),
        "manifest_sha256": sha256_file(manifest_path),
    }


class Phase25PrerequisiteRecovery:
    """Recover exact Phase25 PIT reference prerequisites without fabricating old events."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = (
            derived
            / "strategy_evaluation"
            / "phase25"
            / "v1"
            / "recovery"
        )

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "recovery_report.json"

    def _sessions(self, through_date: date) -> tuple[date, ...]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25PrerequisiteRecoveryError(
                "through-date predates the accepted Phase25 replay origin"
            )
        if not self.calendar.is_session(through_date):
            raise Phase25PrerequisiteRecoveryError(
                f"through-date is not an exchange session: {through_date}"
            )
        sessions = tuple(
            self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date)
        )
        if (
            not sessions
            or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN
            or sessions[-1] != through_date
        ):
            raise Phase25PrerequisiteRecoveryError(
                "recovery exchange-session scope mismatch"
            )
        return sessions

    def _classify_pair(
        self, session: date
    ) -> tuple[str, dict[str, object] | None, str | None]:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest = self.paths.reference_snapshot_manifest(session)
        snapshot_exists = snapshot.is_file()
        manifest_exists = manifest.is_file()
        if not snapshot_exists and not manifest_exists:
            return "missing", None, "both source artifacts are absent"
        if snapshot_exists != manifest_exists:
            return "invalid", None, "source pair is partial"
        try:
            evidence = Phase25Gate5BulkAcquisition(self.settings)._validate_pair(session)  # noqa: SLF001
        except Exception as exc:
            return "invalid", None, f"{type(exc).__name__}: {exc}"
        if evidence is None:
            return "missing", None, "validated pair unexpectedly absent"
        return (
            "valid",
            {
                "session": session.isoformat(),
                "row_count": int(evidence["row_count"]),
                "instrument_count": int(evidence["instrument_count"]),
                "snapshot_sha256": str(evidence["snapshot_sha256"]),
                "manifest_sha256": str(evidence["manifest_sha256"]),
            },
            None,
        )

    def _quarantine_source_pair(
        self,
        *,
        session: date,
        quarantine_root: Path,
        reason: str,
    ) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        quarantine = quarantine_root / f"date={session}"
        quarantine.mkdir(parents=True, exist_ok=True)
        for source in (
            self.paths.reference_snapshot_file(session),
            self.paths.reference_snapshot_manifest(session),
        ):
            if not source.exists():
                continue
            digest: str | None
            try:
                digest = sha256_file(source)
            except OSError:
                digest = None
            destination = quarantine / source.name
            if destination.exists():
                raise Phase25PrerequisiteRecoveryError(
                    f"quarantine destination already exists: {destination}"
                )
            shutil.move(str(source), str(destination))
            records.append(
                {
                    "session": session.isoformat(),
                    "reason": reason,
                    "original_path": str(source.resolve()),
                    "quarantine_path": str(destination.resolve()),
                    "original_sha256": digest,
                }
            )
        return records

    def _persist_reacquired_rows(
        self,
        *,
        session: date,
        rows: list[dict[str, Any]],
    ) -> dict[str, object]:
        if not rows:
            raise Phase25PrerequisiteRecoveryError(
                f"Massive returned zero active stock rows: {session}"
            )
        if any(not str(row.get("ticker") or "").strip() for row in rows):
            raise Phase25PrerequisiteRecoveryError(
                f"Massive returned a blank ticker: {session}"
            )
        if any(row.get("active") is not True for row in rows):
            raise Phase25PrerequisiteRecoveryError(
                f"Massive active-only recovery returned inactive rows: {session}"
            )

        snapshot = self.paths.reference_snapshot_file(session)
        manifest = self.paths.reference_snapshot_manifest(session)
        if snapshot.exists() or manifest.exists():
            raise Phase25PrerequisiteRecoveryError(
                f"recovery refuses to overwrite live source artifacts: {session}"
            )

        registry = InstrumentRegistryStore(self.settings)
        observations = [registry._observation(row, session) for row in rows]  # noqa: SLF001
        row_count = registry._write_snapshot(observations, snapshot)  # noqa: SLF001
        instrument_count = len({item.instrument_id for item in observations})
        atomic_write_text(
            manifest,
            json.dumps(
                {
                    "as_of_date": session.isoformat(),
                    "include_inactive": False,
                    "contract_version": REFERENCE_CONTRACT_VERSION,
                    "identity_contract_version": IDENTITY_CONTRACT_VERSION,
                    "row_count": row_count,
                    "instrument_count": instrument_count,
                    "fetched_at_utc": datetime.now(UTC).isoformat(),
                    "recovery_contract_version": (
                        PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        return _validate_reference_pair_independently(self.paths, session)

    def run(
        self,
        *,
        through_date: date,
        allow_provider_recovery: bool = False,
        progress_callback: Any | None = None,
    ) -> dict[str, object]:
        sessions = self._sessions(through_date)
        states: dict[date, tuple[str, dict[str, object] | None, str | None]] = {
            session: self._classify_pair(session) for session in sessions
        }
        missing = [session for session, state in states.items() if state[0] == "missing"]
        invalid = [session for session, state in states.items() if state[0] == "invalid"]

        if (missing or invalid) and not allow_provider_recovery:
            examples = [
                f"{session}:{states[session][0]}:{states[session][2]}"
                for session in (*missing, *invalid)[:12]
            ]
            raise Phase25PrerequisiteRecoveryError(
                "authoritative provider recovery is required for "
                f"{len(missing)} missing and {len(invalid)} invalid PIT reference sessions; "
                "rerun with explicit provider-recovery authority. Examples: "
                + " | ".join(examples)
            )

        report_path = self.report_path(through_date)
        prior_report_sha256 = sha256_file(report_path) if report_path.is_file() else None

        reused: list[str] = []
        reacquired: list[str] = []
        quarantined: list[dict[str, object]] = []
        acquisition_events: list[dict[str, object]] = []
        provider_page_reads = 0

        attempt_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine_root = (
            self.run_root(through_date)
            / "quarantine"
            / f"attempt={attempt_id}"
        )

        client: _CountingMassiveRESTClient | None = None
        provider: MassiveReferenceProvider | None = None
        if missing or invalid:
            client = _CountingMassiveRESTClient(self.settings)
            provider = MassiveReferenceProvider(self.settings, client=client)

        for index, session in enumerate(sessions, start=1):
            state, evidence, reason = states[session]
            if state == "valid":
                reused.append(session.isoformat())
                if progress_callback is not None:
                    progress_callback(
                        index=index,
                        total=len(sessions),
                        session=session,
                        action="REUSE_VALID",
                    )
                continue

            if provider is None or client is None:
                raise Phase25PrerequisiteRecoveryError(
                    "provider recovery was required but no explicit authority was installed"
                )
            if state == "invalid":
                quarantined.extend(
                    self._quarantine_source_pair(
                        session=session,
                        quarantine_root=quarantine_root,
                        reason=str(reason or "invalid source pair"),
                    )
                )

            before_pages = client.logical_page_reads
            rows = provider.stock_snapshot(session, include_inactive=False)
            raw_row_fingerprint = _stable_hash(rows)
            repaired = self._persist_reacquired_rows(session=session, rows=rows)
            pages = client.logical_page_reads - before_pages
            provider_page_reads = client.logical_page_reads
            reacquired.append(session.isoformat())
            acquisition_events.append(
                {
                    "session": session.isoformat(),
                    "prior_state": state,
                    "prior_reason": reason,
                    "provider": PHASE25_PREREQUISITE_RECOVERY_PROVIDER,
                    "read_class": PHASE25_PREREQUISITE_RECOVERY_READ_CLASS,
                    "provider_page_reads": pages,
                    "raw_row_count": len(rows),
                    "raw_row_fingerprint": raw_row_fingerprint,
                    "persisted_row_count": int(repaired["row_count"]),
                    "persisted_instrument_count": int(repaired["instrument_count"]),
                    "snapshot_sha256": str(repaired["snapshot_sha256"]),
                    "manifest_sha256": str(repaired["manifest_sha256"]),
                }
            )
            if progress_callback is not None:
                progress_callback(
                    index=index,
                    total=len(sessions),
                    session=session,
                    action="REACQUIRE_AUTHORITATIVE",
                    pages=pages,
                    rows=int(repaired["row_count"]),
                )

        source_evidence = [
            _validate_reference_pair_independently(self.paths, session)
            for session in sessions
        ]
        source_lineage_sha256 = _stable_hash(source_evidence)

        # If a prior passing recovery report is still bound to the exact same source
        # lineage, preserve it byte-for-byte so downstream SHA bindings stay stable.
        if not reacquired and report_path.is_file():
            try:
                existing = _read_json(report_path)
            except Phase25PrerequisiteRecoveryError:
                existing = {}
            if (
                existing.get("contract_version")
                == PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION
                and existing.get("through_date") == through_date.isoformat()
                and existing.get("source_lineage_sha256") == source_lineage_sha256
                and existing.get("pass") is True
            ):
                return existing

        report: dict[str, object] = {
            "contract_version": PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION,
            "provenance_mode": "AUTHORITATIVE_RECOVERY_NOT_ORIGINAL_ACQUISITION_HISTORY",
            "through_date": through_date.isoformat(),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "required_session_count": len(sessions),
            "source_sessions": [session.isoformat() for session in sessions],
            "source_evidence": source_evidence,
            "source_lineage_sha256": source_lineage_sha256,
            "validated_reused_sessions": reused,
            "reacquired_sessions": reacquired,
            "quarantined_artifacts": quarantined,
            "acquisition_events": acquisition_events,
            "recovery_provider": PHASE25_PREREQUISITE_RECOVERY_PROVIDER,
            "recovery_read_class": PHASE25_PREREQUISITE_RECOVERY_READ_CLASS,
            "recovery_provider_page_reads": provider_page_reads,
            "provider_recovery_explicitly_authorized": allow_provider_recovery,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "protected_strategy_evidence_reads": 0,
            "phase26_strategy_returns_read": False,
            "synthetic_reference_reconstruction_used": False,
            "original_gate3_gate4_gate5_event_history_recreated": False,
            "global_registry_rebuilt": False,
            "prior_recovery_report_sha256": prior_report_sha256,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": (
                len(source_evidence) == len(sessions)
                and len(reused) + len(reacquired) == len(sessions)
                and set(reacquired)
                == {session.isoformat() for session in (*missing, *invalid)}
                and (not reacquired or provider_page_reads > 0)
            ),
        }
        if report["pass"] is not True:
            raise Phase25PrerequisiteRecoveryError(
                "Phase25 prerequisite recovery acceptance checks failed"
            )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report


class Phase25PrerequisiteRecoveryIndependentValidator:
    """Independently re-open every exact source pair used by recovery."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.recovery = Phase25PrerequisiteRecovery(settings)

    def report_path(self, through_date: date) -> Path:
        return self.recovery.run_root(through_date) / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        recovery_path = self.recovery.report_path(through_date)
        recovery = _read_json(recovery_path)
        if (
            recovery.get("contract_version")
            != PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION
        ):
            raise Phase25PrerequisiteRecoveryError(
                "recovery report contract mismatch"
            )
        if recovery.get("through_date") != through_date.isoformat():
            raise Phase25PrerequisiteRecoveryError(
                "recovery report through-date mismatch"
            )
        if recovery.get("pass") is not True:
            raise Phase25PrerequisiteRecoveryError(
                "recovery report is not passing"
            )
        if recovery.get("provenance_mode") != (
            "AUTHORITATIVE_RECOVERY_NOT_ORIGINAL_ACQUISITION_HISTORY"
        ):
            raise Phase25PrerequisiteRecoveryError(
                "recovery provenance mode is not explicit"
            )
        if recovery.get("original_gate3_gate4_gate5_event_history_recreated") is not False:
            raise Phase25PrerequisiteRecoveryError(
                "recovery report claims recreated historical acquisition events"
            )

        sessions = tuple(
            self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date)
        )
        if (
            not sessions
            or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN
            or sessions[-1] != through_date
        ):
            raise Phase25PrerequisiteRecoveryError(
                "independent recovery session scope mismatch"
            )
        expected_session_text = [session.isoformat() for session in sessions]
        if recovery.get("source_sessions") != expected_session_text:
            raise Phase25PrerequisiteRecoveryError(
                "recovery source-session set/order mismatch"
            )

        evidence = [
            _validate_reference_pair_independently(self.paths, session)
            for session in sessions
        ]
        lineage_sha256 = _stable_hash(evidence)
        if recovery.get("source_evidence") != evidence:
            raise Phase25PrerequisiteRecoveryError(
                "recovery per-session source evidence mismatch"
            )
        if recovery.get("source_lineage_sha256") != lineage_sha256:
            raise Phase25PrerequisiteRecoveryError(
                "recovery source-lineage SHA mismatch"
            )

        reacquired = recovery.get("reacquired_sessions")
        if not isinstance(reacquired, list):
            raise Phase25PrerequisiteRecoveryError(
                "recovery reacquired-session list is malformed"
            )
        if not set(str(item) for item in reacquired).issubset(set(expected_session_text)):
            raise Phase25PrerequisiteRecoveryError(
                "recovery contains out-of-scope reacquired sessions"
            )
        provider_pages = int(recovery.get("recovery_provider_page_reads", -1))
        if reacquired and provider_pages <= 0:
            raise Phase25PrerequisiteRecoveryError(
                "reacquisition is not backed by positive provider-read evidence"
            )
        if not reacquired and provider_pages != 0:
            raise Phase25PrerequisiteRecoveryError(
                "provider-read accounting is nonzero without reacquisition"
            )

        zero_fields = (
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "protected_strategy_evidence_reads",
        )
        for key in zero_fields:
            if int(recovery.get(key, -1)) != 0:
                raise Phase25PrerequisiteRecoveryError(
                    f"recovery authority counter is nonzero: {key}"
                )
        if recovery.get("phase26_strategy_returns_read") is not False:
            raise Phase25PrerequisiteRecoveryError(
                "recovery read Phase26 strategy returns"
            )
        if recovery.get("synthetic_reference_reconstruction_used") is not False:
            raise Phase25PrerequisiteRecoveryError(
                "recovery used synthetic reference reconstruction"
            )

        validation_path = self.report_path(through_date)
        recovery_sha = sha256_file(recovery_path)
        if validation_path.is_file():
            try:
                existing = _read_json(validation_path)
            except Phase25PrerequisiteRecoveryError:
                existing = {}
            if (
                existing.get("contract_version")
                == PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION
                and existing.get("recovery_report_sha256") == recovery_sha
                and existing.get("source_lineage_sha256") == lineage_sha256
                and existing.get("pass") is True
            ):
                return existing

        validation: dict[str, object] = {
            "contract_version": (
                PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION
            ),
            "through_date": through_date.isoformat(),
            "required_session_count": len(sessions),
            "recovery_report_sha256": recovery_sha,
            "source_lineage_sha256": lineage_sha256,
            "provider_recovery_sessions": len(reacquired),
            "recovery_provider_page_reads": provider_pages,
            "checks": {
                "exact_exchange_session_scope": True,
                "all_source_pairs_reopened": True,
                "all_source_pairs_contract_valid": True,
                "all_source_hashes_match_report": True,
                "historical_event_log_not_fabricated": True,
                "provider_write_authority_zero": True,
                "broker_order_paper_live_authority_zero": True,
                "protected_phase26_returns_unread": True,
                "synthetic_reference_reconstruction_false": True,
            },
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(validation_path.resolve()),
            "pass": True,
        }
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            validation_path,
            json.dumps(validation, indent=2, sort_keys=True) + "\n",
        )
        return validation
