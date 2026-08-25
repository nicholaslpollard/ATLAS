from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase25_gate5 import Phase25Gate5BulkAcquisition
from .phase25_gate5_validation import Phase25Gate5IndependentValidator
from .phase25_gate6 import (
    PHASE25_GATE6_POPULATION_CONTRACT_VERSION,
    PHASE25_GATE6_REPORT_CONTRACT_VERSION,
    PHASE25_GATE6_SESSION_SUMMARY_CONTRACT_VERSION,
    Phase25Gate6DiscoveryReconstruction,
)
from .phase25_gate6_policy import phase25_gate6_policy_fingerprint
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


PHASE25_GATE6_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate6-validation-v1-complete-phase7-discovery-research-population"
)


class Phase25Gate6IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate6IndependentValidationError(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate6IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate6IndependentValidationError(f"JSON evidence must be an object: {path}")
    return value


class Phase25Gate6IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate6"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate6DiscoveryReconstruction(self.settings)
        gate6_path = gate.report_path(through_date)
        gate6 = _read_json(gate6_path)
        if gate6.get("contract_version") != PHASE25_GATE6_REPORT_CONTRACT_VERSION:
            raise Phase25Gate6IndependentValidationError("Gate6 report contract mismatch")
        if gate6.get("phase25_gate6_policy_fingerprint") != phase25_gate6_policy_fingerprint():
            raise Phase25Gate6IndependentValidationError("Gate6 policy fingerprint mismatch")
        if gate6.get("through_date") != through_date.isoformat() or gate6.get("pass") is not True:
            raise Phase25Gate6IndependentValidationError("Gate6 report is not passing for through-date")

        gate5_path = Phase25Gate5BulkAcquisition(self.settings).report_path(through_date)
        gate5_validation_path = Phase25Gate5IndependentValidator(self.settings).report_path(through_date)
        if gate6.get("gate5_report_sha256") != sha256_file(gate5_path):
            raise Phase25Gate6IndependentValidationError("Gate6 is not bound to exact Gate5 report")
        if gate6.get("gate5_validation_sha256") != sha256_file(gate5_validation_path):
            raise Phase25Gate6IndependentValidationError("Gate6 is not bound to exact Gate5 validation")

        sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date))
        if not sessions or sessions[-1] != through_date:
            raise Phase25Gate6IndependentValidationError("Gate6 exchange-session scope mismatch")
        if int(gate6.get("replay_session_count", -1)) != len(sessions):
            raise Phase25Gate6IndependentValidationError("Gate6 replay-session count mismatch")

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
            raise Phase25Gate6IndependentValidationError(
                "Gate6 standard lineage remains incomplete: " + ", ".join(missing_standard[:10])
            )

        summary_path = gate.session_summary_path(through_date)
        population_path = gate.population_path(through_date)
        if not summary_path.is_file() or not population_path.is_file():
            raise Phase25Gate6IndependentValidationError("Gate6 research artifacts are missing")
        if gate6.get("session_summary_sha256") != sha256_file(summary_path):
            raise Phase25Gate6IndependentValidationError("Gate6 summary SHA mismatch")
        if gate6.get("population_sha256") != sha256_file(population_path):
            raise Phase25Gate6IndependentValidationError("Gate6 population SHA mismatch")

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
            "gate6_exact_policy": gate6.get("phase25_gate6_policy_fingerprint") == phase25_gate6_policy_fingerprint(),
            "complete_standard_lineage": not missing_standard,
            "summary_exact_sessions": summary_rows == len(sessions) and int(summary[1]) == len(sessions),
            "summary_exact_range": str(summary[2]) == sessions[0].isoformat() and str(summary[3]) == sessions[-1].isoformat(),
            "summary_contract_exact": int(summary[4]) == 0,
            "population_count_matches_summary": population_rows == summed_directional == int(gate6.get("warm_hot_directional_population_rows", -1)),
            "population_contract_exact": int(population[2]) == 0,
            "population_states_exact": int(population[3]) == 0,
            "population_directional_exact": int(population[4]) == 0,
            "population_unique_session_instrument": int(population[5]) == 0,
            "population_range_bounded": population_rows == 0 or (str(population[6]) >= sessions[0].isoformat() and str(population[7]) <= sessions[-1].isoformat()),
            "provider_activity_zero": int(gate6.get("provider_reads", -1)) == 0 and int(gate6.get("provider_writes", -1)) == 0,
            "operational_discovery_state_writes_zero": int(gate6.get("operational_discovery_state_writes", -1)) == 0,
            "strategy_returns_unread": gate6.get("strategy_returns_read") is False,
            "regime_routing_not_run": gate6.get("regime_routing_performed") is False,
            "strategy_rules_not_run": gate6.get("strategy_rule_evaluation_performed") is False,
            "support_authority_false": gate6.get("support_replacement_authority") is False,
            "broker_order_paper_live_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
            "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
            "protected_evidence_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate6IndependentValidationError(
                "Gate6 independent validation failed: " + ", ".join(failed)
            )

        path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE6_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "replay_session_count": len(sessions),
            "gate6_report_sha256": sha256_file(gate6_path),
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
