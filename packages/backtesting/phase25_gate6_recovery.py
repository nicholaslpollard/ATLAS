from __future__ import annotations

import json
from datetime import UTC, date, datetime

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase25_gate6 import (
    PHASE25_GATE6_POPULATION_CONTRACT_VERSION,
    PHASE25_GATE6_REPORT_CONTRACT_VERSION,
    PHASE25_GATE6_SESSION_SUMMARY_CONTRACT_VERSION,
    Phase25Gate6DiscoveryReconstruction,
)
from .phase25_gate6_policy import phase25_gate6_policy_fingerprint
from .phase25_gate6_repair import (
    PHASE25_GATE6_REPAIR_CONTRACT_VERSION,
    Phase25Gate6SafeDiscoveryReconstruction,
)
from .phase25_gate6_validation import PHASE25_GATE6_VALIDATION_CONTRACT_VERSION
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_ROUTE_REPLAY_ORIGIN,
)
from .phase25_prerequisite_recovery import (
    PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION,
    PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION,
    Phase25PrerequisiteRecovery,
    Phase25PrerequisiteRecoveryIndependentValidator,
)


PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION = (
    "phase25-gate6-recovery-binding-v1-authoritative-pit-prerequisite"
)


class Phase25Gate6RecoveryError(RuntimeError):
    pass


def _read_json(path):  # type: ignore[no-untyped-def]
    if not path.is_file():
        raise Phase25Gate6RecoveryError(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate6RecoveryError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate6RecoveryError(f"JSON evidence must be an object: {path}")
    return value


class Phase25Gate6RecoveredPrerequisiteReconstruction(
    Phase25Gate6SafeDiscoveryReconstruction
):
    """Run the accepted Gate6 reconstruction from independently recovered PIT lineage."""

    def _gate5_evidence(self, through_date: date):  # type: ignore[no-untyped-def]
        recovery = Phase25PrerequisiteRecovery(self.settings)
        report_path = recovery.report_path(through_date)
        report = _read_json(report_path)
        if (
            report.get("contract_version")
            != PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION
        ):
            raise Phase25Gate6RecoveryError("recovery prerequisite contract mismatch")
        if report.get("through_date") != through_date.isoformat() or report.get("pass") is not True:
            raise Phase25Gate6RecoveryError(
                "recovery prerequisite is not passing for requested through-date"
            )
        if report.get("provenance_mode") != (
            "AUTHORITATIVE_RECOVERY_NOT_ORIGINAL_ACQUISITION_HISTORY"
        ):
            raise Phase25Gate6RecoveryError("recovery prerequisite provenance mode mismatch")
        if report.get("original_gate3_gate4_gate5_event_history_recreated") is not False:
            raise Phase25Gate6RecoveryError(
                "recovery prerequisite may not recreate historical acquisition events"
            )

        validator = Phase25PrerequisiteRecoveryIndependentValidator(self.settings)
        validation_path = validator.report_path(through_date)
        validation = _read_json(validation_path)
        if (
            validation.get("contract_version")
            != PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION
        ):
            raise Phase25Gate6RecoveryError(
                "recovery independent-validation contract mismatch"
            )
        if validation.get("through_date") != through_date.isoformat():
            raise Phase25Gate6RecoveryError(
                "recovery independent-validation through-date mismatch"
            )
        if validation.get("pass") is not True:
            raise Phase25Gate6RecoveryError(
                "recovery independent validation is not passing"
            )
        if validation.get("recovery_report_sha256") != sha256_file(report_path):
            raise Phase25Gate6RecoveryError(
                "recovery validation is not bound to exact recovery report"
            )
        if validation.get("source_lineage_sha256") != report.get("source_lineage_sha256"):
            raise Phase25Gate6RecoveryError(
                "recovery report/validation source-lineage mismatch"
            )
        return report_path, report, validation_path, validation

    def run(self, *, through_date: date, progress_callback=None):  # type: ignore[no-untyped-def]
        report = super().run(
            through_date=through_date,
            progress_callback=progress_callback,
        )
        recovery_path = str(report.pop("gate5_report_path"))
        recovery_sha = str(report.pop("gate5_report_sha256"))
        recovery_validation_path = str(report.pop("gate5_validation_path"))
        recovery_validation_sha = str(report.pop("gate5_validation_sha256"))
        report.pop("gate5_provider_page_reads", None)

        recovery = _read_json(Phase25PrerequisiteRecovery(self.settings).report_path(through_date))
        report.update(
            {
                "gate6_recovery_binding_contract_version": (
                    PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION
                ),
                "reference_prerequisite_mode": "authoritative_recovery",
                "reference_prerequisite_report_path": recovery_path,
                "reference_prerequisite_report_sha256": recovery_sha,
                "reference_prerequisite_validation_path": recovery_validation_path,
                "reference_prerequisite_validation_sha256": recovery_validation_sha,
                "reference_recovery_provider_page_reads": int(
                    recovery.get("recovery_provider_page_reads", 0)
                ),
                "reference_recovery_reacquired_sessions": len(
                    recovery.get("reacquired_sessions") or []
                ),
                "original_gate5_event_history_recreated": False,
                "gate5_report_path": None,
                "gate5_report_sha256": None,
                "gate5_validation_path": None,
                "gate5_validation_sha256": None,
                "gate5_provider_page_reads": None,
            }
        )
        path = self.report_path(through_date)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


class Phase25Gate6RecoveredIndependentValidator:
    """Gate6 validator that accepts only the explicit authoritative-recovery binding."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate6"

    def report_path(self, through_date: date):  # type: ignore[no-untyped-def]
        return self.root / f"through={through_date}" / "independent_validation.json"

    def _validate_recovery_binding(
        self,
        *,
        through_date: date,
        gate6: dict[str, object],
    ) -> tuple[str, str]:
        if gate6.get("reference_prerequisite_mode") != "authoritative_recovery":
            raise Phase25Gate6RecoveryError(
                "Gate6 recovery validator requires authoritative_recovery prerequisite mode"
            )
        if (
            gate6.get("gate6_recovery_binding_contract_version")
            != PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION
        ):
            raise Phase25Gate6RecoveryError("Gate6 recovery-binding contract mismatch")
        if gate6.get("original_gate5_event_history_recreated") is not False:
            raise Phase25Gate6RecoveryError(
                "Gate6 report may not claim recreated Gate5 event history"
            )
        if any(
            gate6.get(key) is not None
            for key in (
                "gate5_report_path",
                "gate5_report_sha256",
                "gate5_validation_path",
                "gate5_validation_sha256",
                "gate5_provider_page_reads",
            )
        ):
            raise Phase25Gate6RecoveryError(
                "Gate6 recovery report contains misleading Gate5 evidence fields"
            )

        recovery = Phase25PrerequisiteRecovery(self.settings)
        recovery_path = recovery.report_path(through_date)
        recovery_validation_path = (
            Phase25PrerequisiteRecoveryIndependentValidator(self.settings)
            .report_path(through_date)
        )
        recovery_report = _read_json(recovery_path)
        recovery_validation = _read_json(recovery_validation_path)
        if (
            recovery_report.get("contract_version")
            != PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION
            or recovery_report.get("pass") is not True
        ):
            raise Phase25Gate6RecoveryError("recovery report is not accepted")
        if (
            recovery_validation.get("contract_version")
            != PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION
            or recovery_validation.get("pass") is not True
        ):
            raise Phase25Gate6RecoveryError("recovery independent validation is not accepted")
        if recovery_validation.get("recovery_report_sha256") != sha256_file(recovery_path):
            raise Phase25Gate6RecoveryError(
                "recovery independent validation is not bound to exact report"
            )

        expected = {
            "reference_prerequisite_report_path": str(recovery_path.resolve()),
            "reference_prerequisite_report_sha256": sha256_file(recovery_path),
            "reference_prerequisite_validation_path": str(
                recovery_validation_path.resolve()
            ),
            "reference_prerequisite_validation_sha256": sha256_file(
                recovery_validation_path
            ),
        }
        for key, value in expected.items():
            if gate6.get(key) != value:
                raise Phase25Gate6RecoveryError(
                    f"Gate6 recovery prerequisite binding mismatch: {key}"
                )
        if gate6.get("reference_recovery_provider_page_reads") != recovery_report.get(
            "recovery_provider_page_reads"
        ):
            raise Phase25Gate6RecoveryError(
                "Gate6 recovery provider-read accounting mismatch"
            )
        return sha256_file(recovery_path), sha256_file(recovery_validation_path)

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate6DiscoveryReconstruction(self.settings)
        gate6_path = gate.report_path(through_date)
        gate6 = _read_json(gate6_path)
        if gate6.get("contract_version") != PHASE25_GATE6_REPORT_CONTRACT_VERSION:
            raise Phase25Gate6RecoveryError("Gate6 report contract mismatch")
        if gate6.get("phase25_gate6_policy_fingerprint") != phase25_gate6_policy_fingerprint():
            raise Phase25Gate6RecoveryError("Gate6 policy fingerprint mismatch")
        if gate6.get("through_date") != through_date.isoformat() or gate6.get("pass") is not True:
            raise Phase25Gate6RecoveryError(
                "Gate6 report is not passing for through-date"
            )
        if gate6.get("gate6_repair_contract_version") != PHASE25_GATE6_REPAIR_CONTRACT_VERSION:
            raise Phase25Gate6RecoveryError(
                "Gate6 recovery did not use the accepted safe-repair reconstruction"
            )

        recovery_sha, recovery_validation_sha = self._validate_recovery_binding(
            through_date=through_date,
            gate6=gate6,
        )

        sessions = tuple(
            self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date)
        )
        if not sessions or sessions[-1] != through_date:
            raise Phase25Gate6RecoveryError("Gate6 exchange-session scope mismatch")
        if int(gate6.get("replay_session_count", -1)) != len(sessions):
            raise Phase25Gate6RecoveryError("Gate6 replay-session count mismatch")

        missing_standard: list[str] = []
        for session in sessions:
            required = (
                self.paths.reference_snapshot_file(session),
                self.paths.reference_snapshot_manifest(session),
                self.paths.universe_snapshot_file(session),
                self.paths.universe_exclusion_file(session),
                self.paths.universe_snapshot_manifest(session),
                self.paths.discovery_snapshot_file(session),
                self.paths.discovery_snapshot_manifest(session),
                self.paths.discovery_score_file(session),
                self.paths.discovery_score_manifest(session),
            )
            for path in required:
                if not path.is_file():
                    missing_standard.append(str(path))
        if missing_standard:
            raise Phase25Gate6RecoveryError(
                "Gate6 standard lineage remains incomplete: "
                + ", ".join(missing_standard[:10])
            )

        summary_path = gate.session_summary_path(through_date)
        population_path = gate.population_path(through_date)
        if not summary_path.is_file() or not population_path.is_file():
            raise Phase25Gate6RecoveryError("Gate6 research artifacts are missing")
        if gate6.get("session_summary_sha256") != sha256_file(summary_path):
            raise Phase25Gate6RecoveryError("Gate6 summary SHA mismatch")
        if gate6.get("population_sha256") != sha256_file(population_path):
            raise Phase25Gate6RecoveryError("Gate6 population SHA mismatch")

        con = connect_utc(":memory:")
        try:
            summary = con.execute(
                f"""
                SELECT count(*), count(DISTINCT as_of_date), min(as_of_date), max(as_of_date),
                       count(*) FILTER (WHERE contract_version <> ?),
                       sum(warm_hot_directional)
                FROM read_parquet({sql_string(summary_path)})
                """,
                [PHASE25_GATE6_SESSION_SUMMARY_CONTRACT_VERSION],
            ).fetchone()
            population = con.execute(
                f"""
                SELECT count(*), count(DISTINCT as_of_date),
                       count(*) FILTER (WHERE contract_version <> ?),
                       count(*) FILTER (WHERE effective_state NOT IN ('warm','hot')),
                       count(*) FILTER (WHERE direction NOT IN ('bullish','bearish')),
                       count(*) - count(DISTINCT CAST(as_of_date AS VARCHAR) || ':' || instrument_id),
                       min(as_of_date), max(as_of_date)
                FROM read_parquet({sql_string(population_path)})
                """,
                [PHASE25_GATE6_POPULATION_CONTRACT_VERSION],
            ).fetchone()
        finally:
            con.close()

        summary_rows = int(summary[0])
        population_rows = int(population[0])
        summed_directional = int(summary[5] or 0)
        checks = {
            "gate6_exact_policy": (
                gate6.get("phase25_gate6_policy_fingerprint")
                == phase25_gate6_policy_fingerprint()
            ),
            "recovery_prerequisite_exact": True,
            "safe_repair_path_used": True,
            "complete_standard_lineage": not missing_standard,
            "summary_exact_sessions": (
                summary_rows == len(sessions) and int(summary[1]) == len(sessions)
            ),
            "summary_exact_range": (
                str(summary[2]) == sessions[0].isoformat()
                and str(summary[3]) == sessions[-1].isoformat()
            ),
            "summary_contract_exact": int(summary[4]) == 0,
            "population_count_matches_summary": (
                population_rows
                == summed_directional
                == int(gate6.get("warm_hot_directional_population_rows", -1))
            ),
            "population_contract_exact": int(population[2]) == 0,
            "population_states_exact": int(population[3]) == 0,
            "population_directional_exact": int(population[4]) == 0,
            "population_unique_session_instrument": int(population[5]) == 0,
            "population_range_bounded": (
                population_rows == 0
                or (
                    str(population[6]) >= sessions[0].isoformat()
                    and str(population[7]) <= sessions[-1].isoformat()
                )
            ),
            "gate6_provider_activity_zero": (
                int(gate6.get("provider_reads", -1)) == 0
                and int(gate6.get("provider_writes", -1)) == 0
            ),
            "operational_discovery_state_writes_zero": (
                int(gate6.get("operational_discovery_state_writes", -1)) == 0
            ),
            "strategy_returns_unread": gate6.get("strategy_returns_read") is False,
            "regime_routing_not_run": gate6.get("regime_routing_performed") is False,
            "strategy_rules_not_run": (
                gate6.get("strategy_rule_evaluation_performed") is False
            ),
            "support_authority_false": gate6.get("support_replacement_authority") is False,
            "broker_order_paper_live_zero": (
                PHASE25_BROKER_READS
                == PHASE25_BROKER_WRITES
                == PHASE25_ORDER_WRITES
                == PHASE25_PAPER_SUBMITS
                == PHASE25_LIVE_WRITES
                == 0
            ),
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_evidence_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate6RecoveryError(
                "Gate6 recovered independent validation failed: " + ", ".join(failed)
            )

        path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE6_VALIDATION_CONTRACT_VERSION,
            "validator_mode": "authoritative_recovery",
            "through_date": through_date.isoformat(),
            "replay_session_count": len(sessions),
            "gate6_report_sha256": sha256_file(gate6_path),
            "reference_prerequisite_report_sha256": recovery_sha,
            "reference_prerequisite_validation_sha256": recovery_validation_sha,
            "session_summary_sha256": sha256_file(summary_path),
            "population_sha256": sha256_file(population_path),
            "warm_hot_directional_population_rows": population_rows,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
