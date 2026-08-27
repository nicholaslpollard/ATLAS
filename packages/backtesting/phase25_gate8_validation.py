from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY
from packages.strategies.rules import RuleStrategy

from .historical_source import HistoricalStrategyResearchSourceResolver
from .phase25_gate8 import (
    PHASE25_GATE8_REPORT_CONTRACT_VERSION,
    PHASE25_GATE8_SIGNAL_CONTRACT_VERSION,
    Phase25Gate8DevelopmentAttribution,
)
from .phase25_gate8_policy import (
    PHASE25_GATE8_DEVELOPMENT_END,
    PHASE25_GATE8_DEVELOPMENT_START,
    PHASE25_GATE8_OUTCOME_CONTRACT_VERSION,
    PHASE25_GATE8_PROTECTED_START,
    phase25_gate8_policy_fingerprint,
)
from .strategy_evaluation import strategy_condition_sql


PHASE25_GATE8_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate8-validation-v1-development-signal-rule-lineage-authority"
)


class Phase25Gate8IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate8IndependentValidationError(f"missing JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate8IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate8IndependentValidationError("Gate8 JSON evidence must be an object")
    return value


class Phase25Gate8IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate8"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate8DevelopmentAttribution(self.settings)
        report_path = gate.report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE8_REPORT_CONTRACT_VERSION:
            raise Phase25Gate8IndependentValidationError("Gate8 report contract mismatch")
        if report.get("phase25_gate8_policy_fingerprint") != phase25_gate8_policy_fingerprint():
            raise Phase25Gate8IndependentValidationError("Gate8 policy fingerprint mismatch")
        if report.get("through_date") != through_date.isoformat() or report.get("pass") is not True:
            raise Phase25Gate8IndependentValidationError("Gate8 report is not passing")
        signals_path = gate.signals_path(through_date)
        if not signals_path.is_file() or report.get("signals_sha256") != sha256_file(signals_path):
            raise Phase25Gate8IndependentValidationError("Gate8 signal artifact missing/hash-mismatched")
        source = self.source_resolver.resolve()
        if report.get("research_source_fingerprint") != source.source_fingerprint:
            raise Phase25Gate8IndependentValidationError("Gate8 research source fingerprint changed")

        con = connect_utc(":memory:")
        try:
            signal_stats = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(DISTINCT CAST(session_date AS VARCHAR) || ':' || instrument_id || ':' || strategy_id) AS unique_rows,
                    count(*) FILTER (WHERE contract_version <> ?) AS bad_contract,
                    count(*) FILTER (WHERE session_date < CAST(? AS DATE) OR session_date > CAST(? AS DATE)) AS outside_development,
                    count(*) FILTER (WHERE session_date >= CAST(? AS DATE)) AS protected_rows,
                    count(*) FILTER (WHERE forward_return IS NULL OR NOT isfinite(forward_return)) AS bad_return,
                    count(*) FILTER (
                        WHERE abs(directional_return - CASE WHEN strategy_direction='LONG' THEN forward_return ELSE -forward_return END) > 1e-12
                    ) AS bad_directional
                FROM read_parquet({sql_string(signals_path)})
                """,
                [
                    PHASE25_GATE8_SIGNAL_CONTRACT_VERSION,
                    PHASE25_GATE8_DEVELOPMENT_START.isoformat(),
                    PHASE25_GATE8_DEVELOPMENT_END.isoformat(),
                    PHASE25_GATE8_PROTECTED_START.isoformat(),
                ],
            ).fetchone()
            bad_rule_rows = 0
            bad_identity_rows = 0
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                if not isinstance(strategy, RuleStrategy):
                    raise Phase25Gate8IndependentValidationError("Gate8 registry contains non-rule strategy")
                condition = strategy_condition_sql(strategy)
                sid = strategy.metadata.strategy_id
                bad_rule_rows += int(
                    con.execute(
                        f"""
                        SELECT count(*)
                        FROM read_parquet({sql_string(signals_path)}) g
                        INNER JOIN {source.source_sql} s
                          ON CAST(s.session_date AS DATE)=CAST(g.session_date AS DATE)
                         AND s.instrument_id=g.instrument_id
                         AND s.symbol=g.ticker
                        WHERE g.strategy_id={sql_string(sid)} AND NOT ({condition})
                        """
                    ).fetchone()[0]
                )
                signal_count = int(
                    con.execute(
                        f"SELECT count(*) FROM read_parquet({sql_string(signals_path)}) WHERE strategy_id={sql_string(sid)}"
                    ).fetchone()[0]
                )
                joined_count = int(
                    con.execute(
                        f"""
                        SELECT count(*)
                        FROM read_parquet({sql_string(signals_path)}) g
                        INNER JOIN {source.source_sql} s
                          ON CAST(s.session_date AS DATE)=CAST(g.session_date AS DATE)
                         AND s.instrument_id=g.instrument_id
                         AND s.symbol=g.ticker
                        WHERE g.strategy_id={sql_string(sid)}
                        """
                    ).fetchone()[0]
                )
                bad_identity_rows += signal_count - joined_count
        finally:
            con.close()

        checks = {
            "policy_exact": report.get("phase25_gate8_policy_fingerprint") == phase25_gate8_policy_fingerprint(),
            "development_bounds_exact": report.get("development_start") == PHASE25_GATE8_DEVELOPMENT_START.isoformat() and report.get("development_end") == PHASE25_GATE8_DEVELOPMENT_END.isoformat(),
            "outcome_contract_exact": report.get("outcome_contract_version") == PHASE25_GATE8_OUTCOME_CONTRACT_VERSION,
            "signals_row_count_exact": int(signal_stats[0]) == int(report.get("development_rule_fired_signal_rows", -1)),
            "signals_unique": int(signal_stats[1]) == int(signal_stats[0]),
            "signal_contract_exact": int(signal_stats[2]) == 0,
            "development_only": int(signal_stats[3]) == 0 and int(signal_stats[4]) == 0,
            "finite_returns": int(signal_stats[5]) == 0,
            "directional_return_exact": int(signal_stats[6]) == 0,
            "all_signal_rules_recompute_true": bad_rule_rows == 0,
            "all_signal_identities_rejoin": bad_identity_rows == 0,
            "provider_activity_zero": int(report.get("provider_reads", -1)) == 0 and int(report.get("provider_writes", -1)) == 0,
            "protected_reads_zero": int(report.get("protected_evidence_reads", -1)) == 0,
            "support_authority_false": report.get("support_replacement_authority") is False and int(report.get("phase11_support_writes", -1)) == 0,
            "broker_execution_zero": int(report.get("broker_reads", -1)) == 0 and int(report.get("broker_writes", -1)) == 0 and int(report.get("order_writes", -1)) == 0 and int(report.get("paper_submits", -1)) == 0 and int(report.get("live_writes", -1)) == 0,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate8IndependentValidationError("Gate8 independent validation failed: " + ", ".join(failed))

        path = self.report_path(through_date)
        validation: dict[str, object] = {
            "contract_version": PHASE25_GATE8_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate8_report_sha256": sha256_file(report_path),
            "signals_sha256": sha256_file(signals_path),
            "signal_rows": int(signal_stats[0]),
            "research_source_fingerprint": source.source_fingerprint,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(validation, indent=2, sort_keys=True) + "\n")
        return validation
