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

from .phase25_gate3 import (
    PHASE25_GATE3_REPORT_CONTRACT_VERSION,
    Phase25Gate3AcquisitionPlan,
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
    PHASE25_GATE4_ABORT_IF_PROBE_TARGET_MATERIALIZED,
    PHASE25_GATE4_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE4_CONTRACT_VERSION,
    PHASE25_GATE4_EXACT_INTERACTIVE_CONFIRMATION_REQUIRED,
    PHASE25_GATE4_MAX_PROBE_SESSIONS,
    PHASE25_GATE4_PERSIST_PROBE_SESSION_ON_SUCCESS,
    PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE4_PROVIDER_WRITES_ALLOWED,
    PHASE25_GATE4_REUSE_MASSIVE_BOUNDED_RETRIES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


PHASE25_GATE4_REPORT_CONTRACT_VERSION = (
    "phase25-gate4-report-v1-earliest-session-active-only-entitlement-probe"
)
PHASE25_GATE4_EXTERNAL_READ_CLASS = "MASSIVE_ACTIVE_ONLY_PIT_REFERENCE_ENTITLEMENT_PROBE"


class Phase25Gate4Error(RuntimeError):
    pass


class Phase25Gate4AuthorizationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate4Error(f"missing required JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate4Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate4Error(f"JSON evidence must be an object: {path}")
    return payload


@dataclass(frozen=True, slots=True)
class Phase25Gate4ReadChallenge:
    through_date: date
    entitlement_probe_session: date
    execution_scope_id: str
    external_read_classes: tuple[str, ...]
    required_confirmation: str

    def public_dict(self) -> dict[str, object]:
        return {
            "through_date": self.through_date.isoformat(),
            "entitlement_probe_session": self.entitlement_probe_session.isoformat(),
            "execution_scope_id": self.execution_scope_id,
            "external_read_classes": list(self.external_read_classes),
        }


@dataclass(frozen=True, slots=True)
class Phase25Gate4ReadAuthority:
    through_date: date
    entitlement_probe_session: date
    execution_scope_id: str
    external_read_classes: tuple[str, ...]
    explicitly_authorized: bool


@dataclass(frozen=True, slots=True)
class Phase25Gate4Preparation:
    through_date: date
    gate3_report_path: Path
    gate3_report_sha256: str
    gate3_source_fingerprint: str
    acquisition_session_count: int
    entitlement_probe_session: date
    challenge: Phase25Gate4ReadChallenge


def build_phase25_gate4_read_challenge(
    *,
    through_date: date,
    entitlement_probe_session: date,
    gate3_report_sha256: str,
    gate3_source_fingerprint: str,
) -> Phase25Gate4ReadChallenge:
    scope_payload = {
        "phase25_gate4_policy_fingerprint": phase25_gate4_policy_fingerprint(),
        "through_date": through_date.isoformat(),
        "entitlement_probe_session": entitlement_probe_session.isoformat(),
        "gate3_report_sha256": gate3_report_sha256,
        "gate3_source_fingerprint": gate3_source_fingerprint,
        "external_read_classes": [PHASE25_GATE4_EXTERNAL_READ_CLASS],
        "query": {
            "method": "GET",
            "endpoint": PHASE25_GATE3_ENDPOINT,
            "market": PHASE25_GATE3_MARKET,
            "date": entitlement_probe_session.isoformat(),
            "active": PHASE25_GATE3_ACTIVE,
            "order": PHASE25_GATE3_ORDER,
            "sort": PHASE25_GATE3_SORT,
            "limit": PHASE25_GATE3_PAGE_LIMIT,
        },
    }
    scope_id = "p25g4-" + _stable_hash(scope_payload)[:40]
    required = (
        "AUTHORIZE_ATLAS_PHASE25_GATE4_PROBE:"
        f"{entitlement_probe_session.isoformat()}:{scope_id}"
    )
    return Phase25Gate4ReadChallenge(
        through_date=through_date,
        entitlement_probe_session=entitlement_probe_session,
        execution_scope_id=scope_id,
        external_read_classes=(PHASE25_GATE4_EXTERNAL_READ_CLASS,),
        required_confirmation=required,
    )


def authorize_phase25_gate4_probe(
    challenge: Phase25Gate4ReadChallenge,
    *,
    confirmation: str,
    explicitly_authorized: bool,
) -> Phase25Gate4ReadAuthority:
    if not PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 provider-read authority is disabled by policy")
    if not explicitly_authorized or confirmation != challenge.required_confirmation:
        raise Phase25Gate4AuthorizationError(
            "exact Phase25 Gate4 run-scoped probe confirmation was not satisfied"
        )
    return Phase25Gate4ReadAuthority(
        through_date=challenge.through_date,
        entitlement_probe_session=challenge.entitlement_probe_session,
        execution_scope_id=challenge.execution_scope_id,
        external_read_classes=challenge.external_read_classes,
        explicitly_authorized=True,
    )


def require_phase25_gate4_probe_authority(
    authority: Phase25Gate4ReadAuthority | None,
    *,
    challenge: Phase25Gate4ReadChallenge,
) -> Phase25Gate4ReadAuthority:
    if authority is None or not authority.explicitly_authorized:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 provider reads are default-deny")
    if authority.through_date != challenge.through_date:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 authority through-date mismatch")
    if authority.entitlement_probe_session != challenge.entitlement_probe_session:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 authority probe-session mismatch")
    if authority.execution_scope_id != challenge.execution_scope_id:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 authority scope mismatch")
    if authority.external_read_classes != challenge.external_read_classes:
        raise Phase25Gate4AuthorizationError("Phase25 Gate4 authority class mismatch")
    return authority


def validate_gate4_probe_rows(rows: list[dict[str, Any]]) -> dict[str, object]:
    if not rows:
        raise Phase25Gate4Error("Massive entitlement probe returned zero stock rows")
    if any(not str(row.get("ticker") or "").strip() for row in rows):
        raise Phase25Gate4Error("Massive entitlement probe returned a blank ticker")
    if any(row.get("active") is not True for row in rows):
        raise Phase25Gate4Error("Massive active-only entitlement probe returned inactive rows")
    return {
        "row_count": len(rows),
        "raw_row_fingerprint": _stable_hash(rows),
    }


class _CountingMassiveRESTClient(MassiveRESTClient):
    """Count logical REST pages while retaining the accepted client's bounded retries."""

    def __init__(self, settings: AtlasSettings) -> None:
        super().__init__(settings)
        self.logical_page_reads = 0

    def get_json(
        self,
        path_or_url: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.logical_page_reads += 1
        return super().get_json(path_or_url, params)


class _FrozenProbeProvider:
    """Persist validated probe rows without issuing a second provider request."""

    def __init__(self, *, session: date, rows: list[dict[str, Any]]) -> None:
        self.session = session
        self.rows = [dict(item) for item in rows]

    def stock_snapshot(
        self,
        as_of_date: date,
        *,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        if as_of_date != self.session:
            raise Phase25Gate4Error("frozen Gate4 provider session mismatch")
        if include_inactive is not False:
            raise Phase25Gate4Error("Gate4 probe persistence must remain active-only")
        return [dict(item) for item in self.rows]


class Phase25Gate4EntitlementProbe:
    """Explicitly authorized one-session Massive historical-reference entitlement probe."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate4"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "entitlement_probe.json"

    def _gate3_evidence(self, through_date: date) -> tuple[Path, dict[str, object]]:
        path = Phase25Gate3AcquisitionPlan(self.settings).report_path(through_date)
        report = _read_json(path)
        if report.get("contract_version") != PHASE25_GATE3_REPORT_CONTRACT_VERSION:
            raise Phase25Gate4Error("Gate3 report contract mismatch")
        if report.get("through_date") != through_date.isoformat():
            raise Phase25Gate4Error("Gate3 report through-date mismatch")
        if report.get("phase25_gate3_policy_fingerprint") != phase25_gate3_policy_fingerprint():
            raise Phase25Gate4Error("Gate3 policy fingerprint mismatch")
        if report.get("pass") is not True:
            raise Phase25Gate4Error("Gate3 acquisition plan is not passing")
        if report.get("recommendation") != (
            "GATE4_IMPLEMENT_EXPLICIT_RUN_SCOPED_ACTIVE_ONLY_MASSIVE_READ_AUTHORITY"
        ):
            raise Phase25Gate4Error("Gate3 recommendation does not authorize Gate4 implementation")
        if report.get("active_only_reference_acquisition_authority") is not False:
            raise Phase25Gate4Error("Gate3 unexpectedly contains provider acquisition authority")
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
                raise Phase25Gate4Error(f"Gate3 authority counter is nonzero: {key}")
        return path, report

    def _assert_probe_target_absent(self, session: date) -> None:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest = self.paths.reference_snapshot_manifest(session)
        snapshot_exists = snapshot.is_file()
        manifest_exists = manifest.is_file()
        if snapshot_exists != manifest_exists:
            raise Phase25Gate4Error(
                f"Gate4 probe target has unreconciled partial local state: {session}"
            )
        if snapshot_exists and PHASE25_GATE4_ABORT_IF_PROBE_TARGET_MATERIALIZED:
            raise Phase25Gate4Error(
                f"Gate4 probe target is already materialized; regenerate the provider-free Gate3 plan: {session}"
            )

    def prepare(self, *, through_date: date) -> Phase25Gate4Preparation:
        gate3_path, gate3 = self._gate3_evidence(through_date)
        acquisition_sessions = gate3.get("acquisition_sessions")
        if not isinstance(acquisition_sessions, list) or not acquisition_sessions:
            raise Phase25Gate4Error("Gate3 contains no acquisition sessions for entitlement probing")
        if int(gate3.get("acquisition_session_count", -1)) != len(acquisition_sessions):
            raise Phase25Gate4Error("Gate3 acquisition-session count mismatch")
        probe_raw = gate3.get("entitlement_probe_session")
        if probe_raw is None or str(probe_raw) != str(acquisition_sessions[0]):
            raise Phase25Gate4Error("Gate3 entitlement probe is not the earliest acquisition session")
        probe_session = date.fromisoformat(str(probe_raw))
        self._assert_probe_target_absent(probe_session)

        query = gate3.get("acquisition_query")
        expected_query = {
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
        }
        if query != expected_query:
            raise Phase25Gate4Error("Gate3 acquisition query drifted from the locked source shape")

        gate3_sha = sha256_file(gate3_path)
        source_fingerprint = str(gate3.get("source_fingerprint") or "")
        if len(source_fingerprint) != 64:
            raise Phase25Gate4Error("Gate3 source fingerprint is missing or malformed")
        challenge = build_phase25_gate4_read_challenge(
            through_date=through_date,
            entitlement_probe_session=probe_session,
            gate3_report_sha256=gate3_sha,
            gate3_source_fingerprint=source_fingerprint,
        )
        return Phase25Gate4Preparation(
            through_date=through_date,
            gate3_report_path=gate3_path,
            gate3_report_sha256=gate3_sha,
            gate3_source_fingerprint=source_fingerprint,
            acquisition_session_count=len(acquisition_sessions),
            entitlement_probe_session=probe_session,
            challenge=challenge,
        )

    def _validate_persisted_probe(self, session: date) -> dict[str, object]:
        snapshot = self.paths.reference_snapshot_file(session)
        manifest_path = self.paths.reference_snapshot_manifest(session)
        if not snapshot.is_file() or not manifest_path.is_file():
            raise Phase25Gate4Error("Gate4 probe persistence did not produce a complete snapshot/manifest pair")
        manifest = _read_json(manifest_path)
        if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
            raise Phase25Gate4Error("Gate4 probe reference contract mismatch")
        if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
            raise Phase25Gate4Error("Gate4 probe identity contract mismatch")
        if manifest.get("as_of_date") != session.isoformat():
            raise Phase25Gate4Error("Gate4 probe manifest session mismatch")
        if manifest.get("include_inactive") is not False:
            raise Phase25Gate4Error("Gate4 probe manifest is not active-only")

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
        row_count = int(row[0])
        instrument_count = int(row[1])
        if row_count <= 0 or instrument_count <= 0:
            raise Phase25Gate4Error("Gate4 probe persisted nonpositive reference counts")
        if int(row[2]) != 0:
            raise Phase25Gate4Error("Gate4 probe persisted inactive reference rows")
        if int(row[3]) != 0:
            raise Phase25Gate4Error("Gate4 probe persisted blank tickers")
        if int(row[4]) != 1 or str(row[5]) != session.isoformat() or str(row[6]) != session.isoformat():
            raise Phase25Gate4Error("Gate4 probe snapshot contains the wrong session date")
        if int(manifest.get("row_count", -1)) != row_count:
            raise Phase25Gate4Error("Gate4 probe manifest row count mismatch")
        if int(manifest.get("instrument_count", -1)) != instrument_count:
            raise Phase25Gate4Error("Gate4 probe manifest instrument count mismatch")
        return {
            "row_count": row_count,
            "instrument_count": instrument_count,
            "snapshot_sha256": sha256_file(snapshot),
            "manifest_sha256": sha256_file(manifest_path),
        }

    def execute_probe(
        self,
        preparation: Phase25Gate4Preparation,
        *,
        read_authority: Phase25Gate4ReadAuthority | None,
    ) -> dict[str, object]:
        require_phase25_gate4_probe_authority(read_authority, challenge=preparation.challenge)
        if PHASE25_GATE4_BULK_ACQUISITION_ALLOWED:
            raise Phase25Gate4Error("Gate4 bulk acquisition must remain disabled")
        if PHASE25_GATE4_MAX_PROBE_SESSIONS != 1:
            raise Phase25Gate4Error("Gate4 probe session limit drifted")
        self._assert_probe_target_absent(preparation.entitlement_probe_session)

        client = _CountingMassiveRESTClient(self.settings)
        provider = MassiveReferenceProvider(self.settings, client=client)
        rows = provider.stock_snapshot(
            preparation.entitlement_probe_session,
            include_inactive=False,
        )
        raw_validation = validate_gate4_probe_rows(rows)

        self._assert_probe_target_absent(preparation.entitlement_probe_session)
        if not PHASE25_GATE4_PERSIST_PROBE_SESSION_ON_SUCCESS:
            raise Phase25Gate4Error("Gate4 policy unexpectedly disabled successful probe persistence")
        frozen_provider = _FrozenProbeProvider(
            session=preparation.entitlement_probe_session,
            rows=rows,
        )
        registry = InstrumentRegistryStore(self.settings, provider=frozen_provider)  # type: ignore[arg-type]
        result = registry.sync_snapshot(
            preparation.entitlement_probe_session,
            include_inactive=False,
            force=False,
        )
        if result.skipped:
            raise Phase25Gate4Error("Gate4 probe persistence unexpectedly skipped")

        persisted = self._validate_persisted_probe(preparation.entitlement_probe_session)
        report_path = self.report_path(preparation.through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE4_REPORT_CONTRACT_VERSION,
            "gate4_policy_contract_version": PHASE25_GATE4_CONTRACT_VERSION,
            "phase25_gate4_policy_fingerprint": phase25_gate4_policy_fingerprint(),
            "phase25_gate3_policy_fingerprint": phase25_gate3_policy_fingerprint(),
            "gate3_report_contract_version": PHASE25_GATE3_REPORT_CONTRACT_VERSION,
            "gate3_report_path": str(preparation.gate3_report_path.resolve()),
            "gate3_report_sha256": preparation.gate3_report_sha256,
            "gate3_source_fingerprint": preparation.gate3_source_fingerprint,
            "through_date": preparation.through_date.isoformat(),
            "entitlement_probe_session": preparation.entitlement_probe_session.isoformat(),
            "execution_scope_id": preparation.challenge.execution_scope_id,
            "external_read_classes": list(preparation.challenge.external_read_classes),
            "query": {
                "method": "GET",
                "endpoint": PHASE25_GATE3_ENDPOINT,
                "market": PHASE25_GATE3_MARKET,
                "date": preparation.entitlement_probe_session.isoformat(),
                "active": PHASE25_GATE3_ACTIVE,
                "order": PHASE25_GATE3_ORDER,
                "sort": PHASE25_GATE3_SORT,
                "limit": PHASE25_GATE3_PAGE_LIMIT,
            },
            "provider_probe_sessions": 1,
            "provider_page_reads": client.logical_page_reads,
            "provider_writes": 0,
            "bulk_acquisition_sessions": 0,
            "bulk_acquisition_authority": PHASE25_GATE4_BULK_ACQUISITION_ALLOWED,
            "remaining_frozen_acquisition_sessions": max(preparation.acquisition_session_count - 1, 0),
            "raw_probe_row_count": int(raw_validation["row_count"]),
            "raw_probe_row_fingerprint": str(raw_validation["raw_row_fingerprint"]),
            "persisted_row_count": int(persisted["row_count"]),
            "persisted_instrument_count": int(persisted["instrument_count"]),
            "snapshot_sha256": str(persisted["snapshot_sha256"]),
            "manifest_sha256": str(persisted["manifest_sha256"]),
            "manifest_include_inactive": False,
            "provider_native_ticker_case_preserved": True,
            "same_host_pagination_enforced_by_massive_client": True,
            "bounded_provider_retries_reused": PHASE25_GATE4_REUSE_MASSIVE_BOUNDED_RETRIES,
            "strategy_returns_read": False,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "recommendation": "GATE5_IMPLEMENT_RESUMABLE_FROZEN_ACTIVE_ONLY_BULK_ACQUISITION",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": (
                client.logical_page_reads > 0
                and int(persisted["row_count"]) > 0
                and PHASE25_GATE4_PROVIDER_WRITES_ALLOWED is False
                and PHASE25_GATE4_BULK_ACQUISITION_ALLOWED is False
                and PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
                and PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
                and PHASE25_PHASE11_SUPPORT_WRITES == 0
                and PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
            ),
        }
        if report["pass"] is not True:
            raise Phase25Gate4Error("Gate4 entitlement-probe acceptance checks failed")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
