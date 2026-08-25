from __future__ import annotations

import json
from datetime import UTC, date, datetime
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
from .phase25_gate4_validation import (
    PHASE25_GATE4_VALIDATION_CONTRACT_VERSION,
    Phase25Gate4IndependentValidator,
)
from .phase25_gate5 import PHASE25_GATE5_REPORT_CONTRACT_VERSION, Phase25Gate5BulkAcquisition
from .phase25_gate5_policy import (
    PHASE25_GATE5_AUTHORIZATION_MODE,
    PHASE25_GATE5_FORCE_REPLACE_ALLOWED,
    PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED,
    PHASE25_GATE5_PROBE_REFETCH_ALLOWED,
    PHASE25_GATE5_PROVIDER_WRITES_ALLOWED,
    phase25_gate5_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


PHASE25_GATE5_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate5-validation-v1-complete-frozen-active-only-reference-lineage"
)


class Phase25Gate5IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate5IndependentValidationError(f"missing JSON evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate5IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase25Gate5IndependentValidationError(f"JSON evidence must be an object: {path}")
    return payload


class Phase25Gate5IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate5"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate5_path = Phase25Gate5BulkAcquisition(self.settings).report_path(through_date)
        gate5 = _read_json(gate5_path)
        if gate5.get("contract_version") != PHASE25_GATE5_REPORT_CONTRACT_VERSION:
            raise Phase25Gate5IndependentValidationError("Gate5 report contract mismatch")
        if gate5.get("phase25_gate5_policy_fingerprint") != phase25_gate5_policy_fingerprint():
            raise Phase25Gate5IndependentValidationError("Gate5 policy fingerprint mismatch")
        if gate5.get("pass") is not True:
            raise Phase25Gate5IndependentValidationError("Gate5 report is not passing")

        gate3_path = Phase25Gate3AcquisitionPlan(self.settings).report_path(through_date)
        gate3 = _read_json(gate3_path)
        if gate3.get("contract_version") != PHASE25_GATE3_REPORT_CONTRACT_VERSION:
            raise Phase25Gate5IndependentValidationError("Gate3 report contract mismatch")
        if gate3.get("phase25_gate3_policy_fingerprint") != phase25_gate3_policy_fingerprint():
            raise Phase25Gate5IndependentValidationError("Gate3 policy fingerprint mismatch")
        if gate5.get("gate3_report_sha256") != sha256_file(gate3_path):
            raise Phase25Gate5IndependentValidationError("Gate5 is not bound to the exact Gate3 plan")

        gate4_path = Phase25Gate4EntitlementProbe(self.settings).report_path(through_date)
        gate4 = _read_json(gate4_path)
        if gate4.get("contract_version") != PHASE25_GATE4_REPORT_CONTRACT_VERSION:
            raise Phase25Gate5IndependentValidationError("Gate4 report contract mismatch")
        if gate4.get("phase25_gate4_policy_fingerprint") != phase25_gate4_policy_fingerprint():
            raise Phase25Gate5IndependentValidationError("Gate4 policy fingerprint mismatch")
        if gate5.get("gate4_report_sha256") != sha256_file(gate4_path):
            raise Phase25Gate5IndependentValidationError("Gate5 is not bound to the exact Gate4 report")

        gate4_validation_path = Phase25Gate4IndependentValidator(self.settings).report_path(through_date)
        gate4_validation = _read_json(gate4_validation_path)
        if gate4_validation.get("contract_version") != PHASE25_GATE4_VALIDATION_CONTRACT_VERSION:
            raise Phase25Gate5IndependentValidationError("Gate4 independent-validation contract mismatch")
        if gate4_validation.get("pass") is not True:
            raise Phase25Gate5IndependentValidationError("Gate4 independent validation is not passing")
        if gate5.get("gate4_validation_sha256") != sha256_file(gate4_validation_path):
            raise Phase25Gate5IndependentValidationError("Gate5 is not bound to exact Gate4 validation")

        acquisition_raw = gate3.get("acquisition_sessions")
        existing_raw = gate3.get("existing_reference_sessions")
        if not isinstance(acquisition_raw, list) or not acquisition_raw:
            raise Phase25Gate5IndependentValidationError("Gate3 acquisition sessions unavailable")
        if not isinstance(existing_raw, list):
            raise Phase25Gate5IndependentValidationError("Gate3 existing reference sessions unavailable")
        acquisition_sessions = [date.fromisoformat(str(item)) for item in acquisition_raw]
        probe_session = acquisition_sessions[0]
        if gate4.get("entitlement_probe_session") != probe_session.isoformat():
            raise Phase25Gate5IndependentValidationError("Gate4 probe session differs from Gate3")

        manifest_counts: dict[date, tuple[int, int]] = {}
        snapshot_hashes: list[tuple[str, str]] = []
        for session in acquisition_sessions:
            snapshot = self.paths.reference_snapshot_file(session)
            manifest_path = self.paths.reference_snapshot_manifest(session)
            if not snapshot.is_file() or not manifest_path.is_file():
                raise Phase25Gate5IndependentValidationError(
                    f"frozen acquisition pair missing after Gate5: {session}"
                )
            manifest = _read_json(manifest_path)
            if manifest.get("contract_version") != REFERENCE_CONTRACT_VERSION:
                raise Phase25Gate5IndependentValidationError(f"reference contract mismatch: {session}")
            if manifest.get("identity_contract_version") != IDENTITY_CONTRACT_VERSION:
                raise Phase25Gate5IndependentValidationError(f"identity contract mismatch: {session}")
            if manifest.get("as_of_date") != session.isoformat():
                raise Phase25Gate5IndependentValidationError(f"manifest session mismatch: {session}")
            if manifest.get("include_inactive") is not False:
                raise Phase25Gate5IndependentValidationError(f"frozen acquisition pair not active-only: {session}")
            rows = int(manifest.get("row_count", -1))
            instruments = int(manifest.get("instrument_count", -1))
            if rows <= 0 or instruments <= 0:
                raise Phase25Gate5IndependentValidationError(f"nonpositive manifest counts: {session}")
            manifest_counts[session] = (rows, instruments)
            snapshot_hashes.append((session.isoformat(), sha256_file(snapshot)))

        target_values = ",".join(
            f"(DATE '{session.isoformat()}')" for session in acquisition_sessions
        )
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                WITH target(session_date) AS (VALUES {target_values})
                SELECT
                    r.as_of_date,
                    count(*) AS row_count,
                    count(DISTINCT instrument_id) AS instrument_count,
                    count(*) FILTER (WHERE active = false OR active IS NULL) AS inactive_count,
                    count(*) FILTER (WHERE trim(ticker) = '') AS blank_ticker_count
                FROM read_parquet({sql_string(self.paths.reference_snapshot_glob())}, union_by_name=true) r
                INNER JOIN target t ON r.as_of_date = t.session_date
                GROUP BY r.as_of_date
                ORDER BY r.as_of_date
                """
            ).fetchall()
        finally:
            con.close()
        observed = {
            date.fromisoformat(str(row[0])): (
                int(row[1]),
                int(row[2]),
                int(row[3]),
                int(row[4]),
            )
            for row in rows
        }
        if set(observed) != set(acquisition_sessions):
            missing = sorted(set(acquisition_sessions) - set(observed))
            raise Phase25Gate5IndependentValidationError(
                "not every frozen acquisition session is present in canonical reference data: "
                + ", ".join(item.isoformat() for item in missing[:10])
            )
        total_rows = 0
        total_instruments = 0
        for session in acquisition_sessions:
            row_count, instrument_count, inactive_count, blank_count = observed[session]
            if inactive_count != 0 or blank_count != 0:
                raise Phase25Gate5IndependentValidationError(
                    f"invalid active-only canonical rows: {session}"
                )
            if manifest_counts[session] != (row_count, instrument_count):
                raise Phase25Gate5IndependentValidationError(
                    f"canonical/manifest count mismatch: {session}"
                )
            total_rows += row_count
            total_instruments += instrument_count

        registry = self.paths.instrument_registry_file()
        ticker_observations = self.paths.ticker_observations_file()
        checks = {
            "exact_gate5_policy": gate5.get("phase25_gate5_policy_fingerprint") == phase25_gate5_policy_fingerprint(),
            "gate3_exact_lineage": gate5.get("gate3_report_sha256") == sha256_file(gate3_path),
            "gate4_exact_lineage": gate5.get("gate4_report_sha256") == sha256_file(gate4_path),
            "gate4_validation_exact_lineage": gate5.get("gate4_validation_sha256") == sha256_file(gate4_validation_path),
            "authorization_is_explicit_cli_command": gate5.get("authorization_mode") == PHASE25_GATE5_AUTHORIZATION_MODE == "EXPLICIT_CLI_SUBCOMMAND",
            "interactive_confirmation_absent": gate5.get("interactive_confirmation_required") is False and PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED is False,
            "probe_not_refetched": int(gate5.get("probe_refetch_sessions", -1)) == 0 and PHASE25_GATE5_PROBE_REFETCH_ALLOWED is False,
            "exact_frozen_acquisition_count": int(gate5.get("frozen_acquisition_session_count", -1)) == len(acquisition_sessions),
            "exact_frozen_bulk_count": int(gate5.get("frozen_bulk_session_count", -1)) == len(acquisition_sessions) - 1,
            "remaining_frozen_bulk_zero": int(gate5.get("remaining_frozen_bulk_sessions", -1)) == 0,
            "validated_bulk_complete": int(gate5.get("validated_bulk_sessions_after_run", -1)) == len(acquisition_sessions) - 1,
            "provider_writes_zero": int(gate5.get("provider_writes", -1)) == 0 and PHASE25_GATE5_PROVIDER_WRITES_ALLOWED is False,
            "force_replace_zero": gate5.get("force_replace_used") is False and PHASE25_GATE5_FORCE_REPLACE_ALLOWED is False,
            "all_acquisition_sessions_materialized": len(observed) == len(acquisition_sessions),
            "all_acquisition_rows_active": all(item[2] == 0 for item in observed.values()),
            "all_acquisition_tickers_nonblank": all(item[3] == 0 for item in observed.values()),
            "registry_rebuilt": registry.is_file() and ticker_observations.is_file(),
            "broker_order_paper_live_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_evidence_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        passed = all(checks.values())
        if not passed:
            failed = [name for name, value in checks.items() if not value]
            raise Phase25Gate5IndependentValidationError(
                "Gate5 independent validation failed: " + ", ".join(failed)
            )

        path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE5_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate5_report_sha256": sha256_file(gate5_path),
            "gate3_report_sha256": sha256_file(gate3_path),
            "gate4_report_sha256": sha256_file(gate4_path),
            "gate4_validation_sha256": sha256_file(gate4_validation_path),
            "existing_reference_session_count_from_gate3": len(existing_raw),
            "frozen_acquisition_session_count": len(acquisition_sessions),
            "frozen_bulk_session_count": len(acquisition_sessions) - 1,
            "active_only_canonical_row_count": total_rows,
            "active_only_canonical_instrument_observations": total_instruments,
            "snapshot_lineage_fingerprint": sha256_file(registry) if registry.is_file() else None,
            "acquisition_snapshot_sha_fingerprint": __import__("hashlib").sha256(
                json.dumps(snapshot_hashes, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
