from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION, InstrumentRegistryStore
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.massive.rest import MassiveRESTClient

from .phase25_gate3 import PHASE25_GATE3_REPORT_CONTRACT_VERSION, Phase25Gate3AcquisitionPlan
from .phase25_gate4 import PHASE25_GATE4_REPORT_CONTRACT_VERSION, Phase25Gate4EntitlementProbe
from .phase25_gate4_validation import (
    PHASE25_GATE4_VALIDATION_CONTRACT_VERSION,
    Phase25Gate4IndependentValidator,
)
from .phase25_gate5_policy import (
    PHASE25_GATE5_AUTHORIZATION_MODE,
    PHASE25_GATE5_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE5_CONTRACT_VERSION,
    PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE,
    PHASE25_GATE5_FORCE_REPLACE_ALLOWED,
    PHASE25_GATE5_GATE3_FROZEN_SCOPE_REQUIRED,
    PHASE25_GATE5_GATE4_ACCEPTANCE_REQUIRED,
    PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED,
    PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED,
    PHASE25_GATE5_PROBE_REFETCH_ALLOWED,
    PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE5_PROVIDER_WRITES_ALLOWED,
    PHASE25_GATE5_RESUMABLE_SAME_COMMAND,
    PHASE25_GATE5_SKIP_ONLY_VALIDATED_PAIRS,
    phase25_gate5_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_GATE3_ACTIVE,
    PHASE25_GATE3_ENDPOINT,
    PHASE25_GATE3_INCLUDE_INACTIVE,
    PHASE25_GATE3_MARKET,
    PHASE25_GATE3_ORDER,
    PHASE25_GATE3_PAGE_LIMIT,
    PHASE25_GATE3_SORT,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


PHASE25_GATE5_REPORT_CONTRACT_VERSION = (
    "phase25-gate5-report-v1-resumable-frozen-active-only-bulk-acquisition"
)
PHASE25_GATE5_EXTERNAL_READ_CLASS = "MASSIVE_ACTIVE_ONLY_PIT_REFERENCE_BULK_READ"


class Phase25Gate5Error(RuntimeError):
    pass


class Phase25Gate5AuthorizationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate5Error(f"missing required JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate5Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate5Error(f"JSON evidence must be an object: {path}")
    return payload


@dataclass(frozen=True, slots=True)
class Phase25Gate5ReadAuthority:
    through_date: date
    execution_scope_id: str
    authorization_mode: str
    explicitly_authorized: bool


@dataclass(frozen=True, slots=True)
class Phase25Gate5Preparation:
    through_date: date
    gate3_report_path: Path
    gate3_report_sha256: str
    gate4_report_path: Path
    gate4_report_sha256: str
    gate4_validation_path: Path
    gate4_validation_sha256: str
    probe_session: date
    frozen_acquisition_sessions: tuple[date, ...]
    frozen_bulk_sessions: tuple[date, ...]
    validated_existing_bulk_sessions: tuple[date, ...]
    missing_bulk_sessions: tuple[date, ...]
    execution_scope_id: str


class _CountingMassiveRESTClient(MassiveRESTClient):
    """Count successful logical page requests while retaining bounded retries."""

    def __init__(self, settings: AtlasSettings) -> None:
        super().__init__(settings)
        self.logical_page_reads = 0

    def get_json(
        self,
        path_or_url: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = super().get_json(path_or_url, params)
        self.logical_page_reads += 1
        return payload


class Phase25Gate5BulkAcquisition:
    """Resumable acquisition of the frozen post-probe Phase25 reference sessions."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate5"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "bulk_acquisition_report.json"

    def progress_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "progress.json"

    def inflight_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "inflight_session.json"

    def _gate3_evidence(self, through_date: date) -> tuple[Path, dict[str, object]]:
        path = Phase25Gate3AcquisitionPlan(self.settings).report_path(through_date)
        report = _read_json(path)
        if report.get("contract_version") != PHASE25_GATE3_REPORT_CONTRACT_VERSION:
            raise Phase25Gate5Error("Gate3 report contract mismatch")
        if report.get("through_date") != through_date.isoformat():
            raise Phase25Gate5Error("Gate3 report through-date mismatch")
        if report.get("phase25_gate3_policy_fingerprint") != phase25_gate3_policy_fingerprint():
            raise Phase25Gate5Error("Gate3 policy fingerprint mismatch")
        if report.get("pass") is not True:
            raise Phase25Gate5Error("Gate3 acquisition plan is not passing")
        return path, report

    def _gate4_evidence(
        self,
        through_date: date,
        gate3_path: Path,
        gate3: dict[str, object],
    ) -> tuple[Path, dict[str, object], Path, dict[str, object]]:
        if not PHASE25_GATE5_GATE4_ACCEPTANCE_REQUIRED:
            raise Phase25Gate5Error("Gate5 unexpectedly disabled Gate4 acceptance binding")
        gate4_path = Phase25Gate4EntitlementProbe(self.settings).report_path(through_date)
        gate4 = _read_json(gate4_path)
        if gate4.get("contract_version") != PHASE25_GATE4_REPORT_CONTRACT_VERSION:
            raise Phase25Gate5Error("Gate4 report contract mismatch")
        if gate4.get("phase25_gate4_policy_fingerprint") != phase25_gate4_policy_fingerprint():
            raise Phase25Gate5Error("Gate4 policy fingerprint mismatch")
        if gate4.get("gate3_report_sha256") != sha256_file(gate3_path):
            raise Phase25Gate5Error("Gate4 is not bound to the exact Gate3 plan")
        if gate4.get("pass") is not True:
            raise Phase25Gate5Error("Gate4 entitlement probe is not passing")
        if gate4.get("recommendation") != "GATE5_IMPLEMENT_RESUMABLE_FROZEN_ACTIVE_ONLY_BULK_ACQUISITION":
            raise Phase25Gate5Error("Gate4 recommendation does not permit Gate5 implementation")
        if int(gate4.get("provider_probe_sessions", -1)) != 1:
            raise Phase25Gate5Error("Gate4 did not prove exactly one entitlement-probe session")
        if int(gate4.get("bulk_acquisition_sessions", -1)) != 0:
            raise Phase25Gate5Error("Gate4 unexpectedly performed bulk acquisition")

        validation_path = Phase25Gate4IndependentValidator(self.settings).report_path(through_date)
        validation = _read_json(validation_path)
        if validation.get("contract_version") != PHASE25_GATE4_VALIDATION_CONTRACT_VERSION:
            raise Phase25Gate5Error("Gate4 independent-validation contract mismatch")
        if validation.get("gate4_report_sha256") != sha256_file(gate4_path):
            raise Phase25Gate5Error("Gate4 validation is not bound to the exact Gate4 report")
        if validation.get("pass") is not True:
            raise Phase25Gate5Error("Gate4 independent validation is not passing")
        return gate4_path, gate4, validation_path, validation

    def _validate_pair(self, session: date) -> dict[str, object] | None:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest_path = self.paths.reference_snapshot_manifest(session)
        snapshot_exists = snapshot.is_file()
        manifest_exists = manifest_path.is_file()
        if not snapshot_exists and not manifest_exists:
            return None
        if snapshot_exists != manifest_exists:
            if PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED:
                raise Phase25Gate5Error(f"unreconciled partial reference pair: {session}")
            return None
        manifest = _read_json(manifest_path)
        if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
            raise Phase25Gate5Error(f"reference contract mismatch: {session}")
        if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
            raise Phase25Gate5Error(f"identity contract mismatch: {session}")
        if manifest.get("as_of_date") != session.isoformat():
            raise Phase25Gate5Error(f"reference manifest session mismatch: {session}")
        if manifest.get("include_inactive") is not False:
            raise Phase25Gate5Error(f"Gate5 resumable pair is not active-only: {session}")

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
            raise Phase25Gate5Error(f"nonpositive persisted reference counts: {session}")
        if int(row[2]) != 0 or int(row[3]) != 0:
            raise Phase25Gate5Error(f"inactive or blank-ticker rows in active-only pair: {session}")
        if int(row[4]) != 1 or str(row[5]) != session.isoformat() or str(row[6]) != session.isoformat():
            raise Phase25Gate5Error(f"reference snapshot session mismatch: {session}")
        if int(manifest.get("row_count", -1)) != rows:
            raise Phase25Gate5Error(f"reference manifest row-count mismatch: {session}")
        if int(manifest.get("instrument_count", -1)) != instruments:
            raise Phase25Gate5Error(f"reference manifest instrument-count mismatch: {session}")
        return {
            "row_count": rows,
            "instrument_count": instruments,
            "snapshot_sha256": sha256_file(snapshot),
            "manifest_sha256": sha256_file(manifest_path),
        }

    def _validate_snapshot_without_manifest(self, session: date) -> dict[str, int]:
        snapshot = self.paths.reference_snapshot_file(session)
        if not snapshot.is_file():
            raise Phase25Gate5Error(f"missing inflight snapshot: {session}")
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
        if int(row[0]) <= 0 or int(row[1]) <= 0:
            raise Phase25Gate5Error(f"inflight snapshot has nonpositive counts: {session}")
        if int(row[2]) != 0 or int(row[3]) != 0:
            raise Phase25Gate5Error(f"inflight snapshot is not valid active-only data: {session}")
        if int(row[4]) != 1 or str(row[5]) != session.isoformat() or str(row[6]) != session.isoformat():
            raise Phase25Gate5Error(f"inflight snapshot session mismatch: {session}")
        return {"row_count": int(row[0]), "instrument_count": int(row[1])}

    def _write_manifest(self, session: date, *, row_count: int, instrument_count: int) -> None:
        atomic_write_text(
            self.paths.reference_snapshot_manifest(session),
            json.dumps(
                {
                    "as_of_date": session.isoformat(),
                    "include_inactive": False,
                    "contract_version": REFERENCE_CONTRACT_VERSION,
                    "identity_contract_version": IDENTITY_CONTRACT_VERSION,
                    "row_count": row_count,
                    "instrument_count": instrument_count,
                    "fetched_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    def _reconcile_inflight(self, through_date: date, allowed_sessions: set[date]) -> None:
        path = self.inflight_path(through_date)
        if not path.is_file():
            return
        inflight = _read_json(path)
        raw_session = str(inflight.get("session") or "")
        try:
            session = date.fromisoformat(raw_session)
        except ValueError as exc:
            raise Phase25Gate5Error("Gate5 inflight marker contains an invalid session") from exc
        if session not in allowed_sessions:
            raise Phase25Gate5Error("Gate5 inflight marker is outside the frozen bulk scope")
        snapshot = self.paths.reference_snapshot_file(session)
        manifest = self.paths.reference_snapshot_manifest(session)
        if not snapshot.is_file() and not manifest.is_file():
            path.unlink(missing_ok=True)
            return
        if manifest.is_file() and not snapshot.is_file():
            raise Phase25Gate5Error(f"unreconciled manifest-only inflight state: {session}")
        if snapshot.is_file() and not manifest.is_file():
            counts = self._validate_snapshot_without_manifest(session)
            expected_rows = int(inflight.get("raw_row_count", -1))
            if expected_rows > 0 and expected_rows != counts["row_count"]:
                raise Phase25Gate5Error(f"inflight snapshot row count differs from fetched evidence: {session}")
            self._write_manifest(
                session,
                row_count=counts["row_count"],
                instrument_count=counts["instrument_count"],
            )
        self._validate_pair(session)
        path.unlink(missing_ok=True)

    def _persist_rows(
        self,
        through_date: date,
        session: date,
        rows: list[dict[str, Any]],
        *,
        raw_row_fingerprint: str,
    ) -> dict[str, object]:
        if any(not str(row.get("ticker") or "").strip() for row in rows):
            raise Phase25Gate5Error(f"Massive returned a blank ticker: {session}")
        if any(row.get("active") is not True for row in rows):
            raise Phase25Gate5Error(f"Massive active-only query returned inactive rows: {session}")
        if not rows:
            raise Phase25Gate5Error(f"Massive returned zero active stock rows: {session}")

        marker = self.inflight_path(through_date)
        marker.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            marker,
            json.dumps(
                {
                    "contract_version": "phase25-gate5-inflight-v1",
                    "session": session.isoformat(),
                    "raw_row_count": len(rows),
                    "raw_row_fingerprint": raw_row_fingerprint,
                    "created_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        registry = InstrumentRegistryStore(self.settings)
        observations = [registry._observation(row, session) for row in rows]  # noqa: SLF001
        target = self.paths.reference_snapshot_file(session)
        row_count = registry._write_snapshot(observations, target)  # noqa: SLF001
        instrument_count = len({obs.instrument_id for obs in observations})
        self._write_manifest(session, row_count=row_count, instrument_count=instrument_count)
        result = self._validate_pair(session)
        if result is None:
            raise Phase25Gate5Error(f"Gate5 persistence unexpectedly produced no pair: {session}")
        marker.unlink(missing_ok=True)
        return result

    def prepare(self, *, through_date: date) -> Phase25Gate5Preparation:
        if not PHASE25_GATE5_GATE3_FROZEN_SCOPE_REQUIRED:
            raise Phase25Gate5Error("Gate5 unexpectedly disabled frozen Gate3 scope")
        gate3_path, gate3 = self._gate3_evidence(through_date)
        gate4_path, gate4, gate4_validation_path, _ = self._gate4_evidence(
            through_date, gate3_path, gate3
        )
        acquisition_raw = gate3.get("acquisition_sessions")
        if not isinstance(acquisition_raw, list) or len(acquisition_raw) < 2:
            raise Phase25Gate5Error("Gate3 frozen acquisition list is unavailable")
        acquisition_sessions = tuple(date.fromisoformat(str(item)) for item in acquisition_raw)
        probe_session = date.fromisoformat(str(gate4.get("entitlement_probe_session")))
        if acquisition_sessions[0] != probe_session:
            raise Phase25Gate5Error("Gate4 probe is not the first frozen Gate3 acquisition session")
        if PHASE25_GATE5_PROBE_REFETCH_ALLOWED:
            raise Phase25Gate5Error("Gate5 probe refetch must remain disabled")
        probe_pair = self._validate_pair(probe_session)
        if probe_pair is None:
            raise Phase25Gate5Error("accepted Gate4 probe pair is missing")
        if gate4.get("snapshot_sha256") != probe_pair["snapshot_sha256"]:
            raise Phase25Gate5Error("accepted Gate4 probe snapshot changed")
        if gate4.get("manifest_sha256") != probe_pair["manifest_sha256"]:
            raise Phase25Gate5Error("accepted Gate4 probe manifest changed")

        bulk_sessions = acquisition_sessions[1:]
        self._reconcile_inflight(through_date, set(bulk_sessions))
        validated: list[date] = []
        missing: list[date] = []
        for session in bulk_sessions:
            pair = self._validate_pair(session)
            if pair is None:
                missing.append(session)
            elif PHASE25_GATE5_SKIP_ONLY_VALIDATED_PAIRS:
                validated.append(session)
            else:
                raise Phase25Gate5Error("Gate5 skip policy drifted from validated-pair-only")

        scope_payload = {
            "phase25_gate5_policy_fingerprint": phase25_gate5_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "gate3_report_sha256": sha256_file(gate3_path),
            "gate4_report_sha256": sha256_file(gate4_path),
            "gate4_validation_sha256": sha256_file(gate4_validation_path),
            "probe_session": probe_session.isoformat(),
            "frozen_bulk_sessions": [item.isoformat() for item in bulk_sessions],
            "external_read_classes": [PHASE25_GATE5_EXTERNAL_READ_CLASS],
            "authorization_mode": PHASE25_GATE5_AUTHORIZATION_MODE,
        }
        execution_scope_id = "p25g5-" + _stable_hash(scope_payload)[:40]
        return Phase25Gate5Preparation(
            through_date=through_date,
            gate3_report_path=gate3_path,
            gate3_report_sha256=sha256_file(gate3_path),
            gate4_report_path=gate4_path,
            gate4_report_sha256=sha256_file(gate4_path),
            gate4_validation_path=gate4_validation_path,
            gate4_validation_sha256=sha256_file(gate4_validation_path),
            probe_session=probe_session,
            frozen_acquisition_sessions=acquisition_sessions,
            frozen_bulk_sessions=bulk_sessions,
            validated_existing_bulk_sessions=tuple(validated),
            missing_bulk_sessions=tuple(missing),
            execution_scope_id=execution_scope_id,
        )

    def authorize_cli_acquire(self, preparation: Phase25Gate5Preparation) -> Phase25Gate5ReadAuthority:
        if not PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED:
            raise Phase25Gate5AuthorizationError("Phase25 Gate5 provider-read authority is disabled")
        if PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED:
            raise Phase25Gate5AuthorizationError("Gate5 interactive confirmation must remain disabled")
        if PHASE25_GATE5_AUTHORIZATION_MODE != "EXPLICIT_CLI_SUBCOMMAND":
            raise Phase25Gate5AuthorizationError("Gate5 authorization mode drifted")
        return Phase25Gate5ReadAuthority(
            through_date=preparation.through_date,
            execution_scope_id=preparation.execution_scope_id,
            authorization_mode=PHASE25_GATE5_AUTHORIZATION_MODE,
            explicitly_authorized=True,
        )

    @staticmethod
    def _require_authority(
        preparation: Phase25Gate5Preparation,
        authority: Phase25Gate5ReadAuthority | None,
    ) -> None:
        if authority is None or not authority.explicitly_authorized:
            raise Phase25Gate5AuthorizationError("Gate5 provider reads are default-deny")
        if authority.through_date != preparation.through_date:
            raise Phase25Gate5AuthorizationError("Gate5 authority through-date mismatch")
        if authority.execution_scope_id != preparation.execution_scope_id:
            raise Phase25Gate5AuthorizationError("Gate5 authority scope mismatch")
        if authority.authorization_mode != "EXPLICIT_CLI_SUBCOMMAND":
            raise Phase25Gate5AuthorizationError("Gate5 authority mode mismatch")

    def _write_progress(
        self,
        preparation: Phase25Gate5Preparation,
        *,
        newly_acquired: int,
        provider_page_reads: int,
        last_completed_session: date | None,
    ) -> None:
        completed = len(preparation.validated_existing_bulk_sessions) + newly_acquired
        atomic_write_text(
            self.progress_path(preparation.through_date),
            json.dumps(
                {
                    "contract_version": "phase25-gate5-progress-v1",
                    "phase25_gate5_policy_fingerprint": phase25_gate5_policy_fingerprint(),
                    "through_date": preparation.through_date.isoformat(),
                    "execution_scope_id": preparation.execution_scope_id,
                    "frozen_bulk_session_count": len(preparation.frozen_bulk_sessions),
                    "validated_before_run": len(preparation.validated_existing_bulk_sessions),
                    "newly_acquired_this_run": newly_acquired,
                    "completed_bulk_sessions": completed,
                    "remaining_bulk_sessions": len(preparation.frozen_bulk_sessions) - completed,
                    "successful_provider_page_reads_this_run": provider_page_reads,
                    "last_completed_session": last_completed_session.isoformat() if last_completed_session else None,
                    "updated_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    def execute(
        self,
        preparation: Phase25Gate5Preparation,
        *,
        read_authority: Phase25Gate5ReadAuthority | None,
        progress_callback: Any | None = None,
    ) -> dict[str, object]:
        self._require_authority(preparation, read_authority)
        if not PHASE25_GATE5_BULK_ACQUISITION_ALLOWED:
            raise Phase25Gate5Error("Gate5 bulk acquisition is disabled")
        if PHASE25_GATE5_FORCE_REPLACE_ALLOWED:
            raise Phase25Gate5Error("Gate5 force-replace must remain disabled")
        if preparation.probe_session in preparation.missing_bulk_sessions:
            raise Phase25Gate5Error("Gate5 would re-fetch the accepted entitlement probe")

        client = _CountingMassiveRESTClient(self.settings)
        provider = MassiveReferenceProvider(self.settings, client=client)
        newly_acquired = 0
        raw_rows_total = 0
        persisted_rows_total = 0
        last_completed: date | None = None

        for index, session in enumerate(preparation.missing_bulk_sessions, start=1):
            before_pages = client.logical_page_reads
            rows = provider.stock_snapshot(session, include_inactive=False)
            raw_fingerprint = _stable_hash(rows)
            persisted = self._persist_rows(
                preparation.through_date,
                session,
                rows,
                raw_row_fingerprint=raw_fingerprint,
            )
            session_pages = client.logical_page_reads - before_pages
            newly_acquired += 1
            raw_rows_total += len(rows)
            persisted_rows_total += int(persisted["row_count"])
            last_completed = session
            self._write_progress(
                preparation,
                newly_acquired=newly_acquired,
                provider_page_reads=client.logical_page_reads,
                last_completed_session=last_completed,
            )
            if progress_callback is not None:
                progress_callback(
                    index=index,
                    total=len(preparation.missing_bulk_sessions),
                    session=session,
                    rows=int(persisted["row_count"]),
                    pages=session_pages,
                )

        post = self.prepare(through_date=preparation.through_date)
        if post.missing_bulk_sessions:
            raise Phase25Gate5Error(
                f"Gate5 acquisition ended with {len(post.missing_bulk_sessions)} frozen sessions still missing"
            )
        if not PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE:
            raise Phase25Gate5Error("Gate5 registry rebuild policy drifted")
        InstrumentRegistryStore(self.settings).rebuild_registry()

        report_path = self.report_path(preparation.through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE5_REPORT_CONTRACT_VERSION,
            "gate5_policy_contract_version": PHASE25_GATE5_CONTRACT_VERSION,
            "phase25_gate5_policy_fingerprint": phase25_gate5_policy_fingerprint(),
            "through_date": preparation.through_date.isoformat(),
            "execution_scope_id": preparation.execution_scope_id,
            "authorization_mode": PHASE25_GATE5_AUTHORIZATION_MODE,
            "interactive_confirmation_required": PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED,
            "external_read_classes": [PHASE25_GATE5_EXTERNAL_READ_CLASS],
            "gate3_report_sha256": preparation.gate3_report_sha256,
            "gate4_report_sha256": preparation.gate4_report_sha256,
            "gate4_validation_sha256": preparation.gate4_validation_sha256,
            "entitlement_probe_session": preparation.probe_session.isoformat(),
            "probe_refetch_sessions": 0,
            "frozen_acquisition_session_count": len(preparation.frozen_acquisition_sessions),
            "frozen_bulk_session_count": len(preparation.frozen_bulk_sessions),
            "validated_bulk_sessions_before_run": len(preparation.validated_existing_bulk_sessions),
            "newly_acquired_bulk_sessions_this_run": newly_acquired,
            "validated_bulk_sessions_after_run": len(post.validated_existing_bulk_sessions),
            "remaining_frozen_bulk_sessions": len(post.missing_bulk_sessions),
            "successful_provider_page_reads_this_run": client.logical_page_reads,
            "raw_rows_acquired_this_run": raw_rows_total,
            "persisted_rows_acquired_this_run": persisted_rows_total,
            "provider_writes": 0,
            "force_replace_used": False,
            "registry_rebuilt_once_after_complete": True,
            "resumable_same_command": PHASE25_GATE5_RESUMABLE_SAME_COMMAND,
            "strategy_returns_read": False,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "recommendation": "GATE6_INDEPENDENT_VALIDATE_AND_REBUILD_PHASE7_UNIVERSE_LINEAGE",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": (
                len(post.validated_existing_bulk_sessions) == len(preparation.frozen_bulk_sessions)
                and len(post.missing_bulk_sessions) == 0
                and PHASE25_GATE5_PROVIDER_WRITES_ALLOWED is False
                and PHASE25_GATE5_FORCE_REPLACE_ALLOWED is False
                and PHASE25_GATE5_PROBE_REFETCH_ALLOWED is False
                and PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
                and PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
                and PHASE25_PHASE11_SUPPORT_WRITES == 0
                and PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
            ),
        }
        if report["pass"] is not True:
            raise Phase25Gate5Error("Gate5 final acceptance checks failed")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
