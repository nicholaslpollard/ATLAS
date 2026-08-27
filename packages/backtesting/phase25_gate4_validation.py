from __future__ import annotations

import json
from datetime import date, datetime, UTC
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.registry import REFERENCE_CONTRACT_VERSION

from .phase25_gate3 import PHASE25_GATE3_REPORT_CONTRACT_VERSION, Phase25Gate3AcquisitionPlan
from .phase25_gate4 import PHASE25_GATE4_REPORT_CONTRACT_VERSION, Phase25Gate4EntitlementProbe
from .phase25_policy import (
    PHASE25_GATE4_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE4_MAX_PROBE_SESSIONS,
    PHASE25_GATE4_PROVIDER_WRITES_ALLOWED,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


PHASE25_GATE4_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate4-validation-v1-persisted-entitlement-probe-no-bulk"
)


class Phase25Gate4IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate4IndependentValidationError(f"missing JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate4IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate4IndependentValidationError(f"JSON evidence must be an object: {path}")
    return payload


class Phase25Gate4IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate4"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate4_path = Phase25Gate4EntitlementProbe(self.settings).report_path(through_date)
        gate4 = _read_json(gate4_path)
        if gate4.get("contract_version") != PHASE25_GATE4_REPORT_CONTRACT_VERSION:
            raise Phase25Gate4IndependentValidationError("Gate4 report contract mismatch")
        if gate4.get("phase25_gate4_policy_fingerprint") != phase25_gate4_policy_fingerprint():
            raise Phase25Gate4IndependentValidationError("Gate4 policy fingerprint mismatch")
        if gate4.get("pass") is not True:
            raise Phase25Gate4IndependentValidationError("Gate4 report is not passing")

        gate3_path = Phase25Gate3AcquisitionPlan(self.settings).report_path(through_date)
        gate3 = _read_json(gate3_path)
        if gate3.get("contract_version") != PHASE25_GATE3_REPORT_CONTRACT_VERSION:
            raise Phase25Gate4IndependentValidationError("Gate3 report contract mismatch")
        if gate3.get("phase25_gate3_policy_fingerprint") != phase25_gate3_policy_fingerprint():
            raise Phase25Gate4IndependentValidationError("Gate3 policy fingerprint mismatch")
        if gate4.get("gate3_report_sha256") != sha256_file(gate3_path):
            raise Phase25Gate4IndependentValidationError("Gate4 is not bound to the exact Gate3 plan")
        if gate4.get("gate3_source_fingerprint") != gate3.get("source_fingerprint"):
            raise Phase25Gate4IndependentValidationError("Gate4 Gate3-source fingerprint mismatch")

        probe_session = date.fromisoformat(str(gate4.get("entitlement_probe_session")))
        if gate3.get("entitlement_probe_session") != probe_session.isoformat():
            raise Phase25Gate4IndependentValidationError("Gate4 probe session differs from Gate3")
        acquisition_sessions = gate3.get("acquisition_sessions")
        if not isinstance(acquisition_sessions, list) or not acquisition_sessions:
            raise Phase25Gate4IndependentValidationError("Gate3 acquisition session list is unavailable")
        if str(acquisition_sessions[0]) != probe_session.isoformat():
            raise Phase25Gate4IndependentValidationError("Gate4 probe was not the earliest frozen session")

        snapshot = self.paths.reference_snapshot_file(probe_session)
        manifest_path = self.paths.reference_snapshot_manifest(probe_session)
        if not snapshot.is_file() or not manifest_path.is_file():
            raise Phase25Gate4IndependentValidationError("Gate4 probe pair is incomplete")
        manifest = _read_json(manifest_path)
        if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
            raise Phase25Gate4IndependentValidationError("reference contract mismatch")
        if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
            raise Phase25Gate4IndependentValidationError("identity contract mismatch")
        if manifest.get("as_of_date") != probe_session.isoformat():
            raise Phase25Gate4IndependentValidationError("reference manifest session mismatch")
        if manifest.get("include_inactive") is not False:
            raise Phase25Gate4IndependentValidationError("reference manifest is not active-only")
        if gate4.get("snapshot_sha256") != sha256_file(snapshot):
            raise Phase25Gate4IndependentValidationError("Gate4 snapshot SHA mismatch")
        if gate4.get("manifest_sha256") != sha256_file(manifest_path):
            raise Phase25Gate4IndependentValidationError("Gate4 manifest SHA mismatch")

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
        checks = {
            "gate4_exact_policy": gate4.get("phase25_gate4_policy_fingerprint") == phase25_gate4_policy_fingerprint(),
            "gate3_exact_lineage": gate4.get("gate3_report_sha256") == sha256_file(gate3_path),
            "earliest_probe_session_exact": str(acquisition_sessions[0]) == probe_session.isoformat(),
            "one_provider_probe_session": int(gate4.get("provider_probe_sessions", -1)) == PHASE25_GATE4_MAX_PROBE_SESSIONS == 1,
            "positive_provider_page_reads": int(gate4.get("provider_page_reads", 0)) > 0,
            "provider_writes_zero": int(gate4.get("provider_writes", -1)) == 0 and PHASE25_GATE4_PROVIDER_WRITES_ALLOWED is False,
            "bulk_acquisition_zero": int(gate4.get("bulk_acquisition_sessions", -1)) == 0 and gate4.get("bulk_acquisition_authority") is False and PHASE25_GATE4_BULK_ACQUISITION_ALLOWED is False,
            "positive_snapshot_counts": rows > 0 and instruments > 0,
            "all_rows_active": int(row[2]) == 0,
            "no_blank_tickers": int(row[3]) == 0,
            "exact_snapshot_session": int(row[4]) == 1 and str(row[5]) == probe_session.isoformat() and str(row[6]) == probe_session.isoformat(),
            "manifest_counts_match": int(manifest.get("row_count", -1)) == rows and int(manifest.get("instrument_count", -1)) == instruments,
            "broker_order_paper_live_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_evidence_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        passed = all(checks.values())
        if not passed:
            failed = [name for name, value in checks.items() if not value]
            raise Phase25Gate4IndependentValidationError("Gate4 independent validation failed: " + ", ".join(failed))

        path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE4_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "entitlement_probe_session": probe_session.isoformat(),
            "gate4_report_sha256": sha256_file(gate4_path),
            "gate3_report_sha256": sha256_file(gate3_path),
            "snapshot_sha256": sha256_file(snapshot),
            "manifest_sha256": sha256_file(manifest_path),
            "persisted_row_count": rows,
            "persisted_instrument_count": instruments,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
