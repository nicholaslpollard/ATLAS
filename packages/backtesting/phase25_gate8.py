from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY
from packages.strategies.rules import RuleStrategy

from .historical_source import HistoricalStrategyResearchSourceResolver
from .phase25_gate7 import (
    PHASE25_GATE7_REPORT_CONTRACT_VERSION,
    PHASE25_GATE7_ROUTE_CONTRACT_VERSION,
    Phase25Gate7RouteContextReplay,
)
from .phase25_gate7_policy import phase25_gate7_policy_fingerprint
from .phase25_gate7_validation import (
    PHASE25_GATE7_VALIDATION_CONTRACT_VERSION,
    Phase25Gate7IndependentValidator,
)
from .phase25_gate8_policy import (
    PHASE25_GATE8_BROAD_COMPARATOR_ALLOWED,
    PHASE25_GATE8_COST_GRID_BPS,
    PHASE25_GATE8_DEVELOPMENT_END,
    PHASE25_GATE8_DEVELOPMENT_START,
    PHASE25_GATE8_OUTCOME_CHANGES_ALLOWED,
    PHASE25_GATE8_OUTCOME_CONTRACT_VERSION,
    PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE8_PROTECTED_START,
    PHASE25_GATE8_PROVIDER_READS,
    PHASE25_GATE8_PROVIDER_WRITES,
    PHASE25_GATE8_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE8_STRATEGY_RULE_CHANGES_ALLOWED,
    PHASE25_GATE8_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate8_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
)
from .strategy_evaluation import StrategyEvaluationEngine, strategy_condition_sql


PHASE25_GATE8_REPORT_CONTRACT_VERSION = (
    "phase25-gate8-report-v1-development-production-path-vs-broad-attribution"
)
PHASE25_GATE8_SIGNAL_CONTRACT_VERSION = (
    "phase25-gate8-signals-v1-route-eligible-rule-fired-three-session"
)


class Phase25Gate8Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate8Error(f"missing required JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate8Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate8Error(f"JSON evidence must be an object: {path}")
    return value


def _primary_mean(summary: dict[str, object]) -> float | None:
    metric = dict(dict(summary["aggregate_by_cost_bps"])["10"])
    value = metric.get("mean_return")
    return None if value is None else float(value)


class Phase25Gate8DevelopmentAttribution:
    """Evaluate unchanged incumbents on development-only Gate7 production routes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.engine = StrategyEvaluationEngine(DEFAULT_STRATEGY_REGISTRY)
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate8"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "development_attribution.json"

    def signals_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "development_signals.parquet"

    def _gate7_evidence(self, through_date: date) -> tuple[Path, Path, Path, dict[str, object]]:
        gate7_runner = Phase25Gate7RouteContextReplay(self.settings)
        report_path = gate7_runner.report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE7_REPORT_CONTRACT_VERSION:
            raise Phase25Gate8Error("Gate7 report contract mismatch")
        if report.get("phase25_gate7_policy_fingerprint") != phase25_gate7_policy_fingerprint():
            raise Phase25Gate8Error("Gate7 policy fingerprint mismatch")
        if report.get("through_date") != through_date.isoformat() or report.get("pass") is not True:
            raise Phase25Gate8Error("Gate7 report is not accepted for requested through-date")
        validation_path = Phase25Gate7IndependentValidator(self.settings).report_path(through_date)
        validation = _read_json(validation_path)
        if validation.get("contract_version") != PHASE25_GATE7_VALIDATION_CONTRACT_VERSION:
            raise Phase25Gate8Error("Gate7 independent-validation contract mismatch")
        if validation.get("pass") is not True:
            raise Phase25Gate8Error("Gate7 independent validation is not passing")
        routes_path = gate7_runner.routes_path(through_date)
        if not routes_path.is_file() or report.get("routes_sha256") != sha256_file(routes_path):
            raise Phase25Gate8Error("Gate7 route decisions are missing or hash-mismatched")
        return report_path, validation_path, routes_path, report

    @staticmethod
    def _write_parquet(settings: AtlasSettings, frame: pd.DataFrame, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("phase25_gate8_frame", frame)
            compression = settings.data.parquet.compression.upper()
            row_group_size = int(settings.data.parquet.row_group_size)
            con.execute(
                f"COPY (SELECT * FROM phase25_gate8_frame ORDER BY session_date, strategy_id, instrument_id) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
                f"ROW_GROUP_SIZE {row_group_size})"
            )
            promote(temp, target)
        finally:
            con.close()

    def _create_joined_view(self, con, *, routes_path: Path, source_sql: str) -> dict[str, int]:
        con.execute(
            f"""
            CREATE TEMP VIEW p25_gate8_routes AS
            SELECT * FROM read_parquet({sql_string(routes_path)})
            WHERE contract_version = {sql_string(PHASE25_GATE7_ROUTE_CONTRACT_VERSION)}
              AND eligible = TRUE
              AND as_of_date >= DATE {sql_string(PHASE25_GATE8_DEVELOPMENT_START.isoformat())}
              AND as_of_date <= DATE {sql_string(PHASE25_GATE8_DEVELOPMENT_END.isoformat())}
            """
        )
        duplicate_source = int(
            con.execute(
                f"""
                SELECT count(*) FROM (
                    SELECT CAST(session_date AS DATE), instrument_id, symbol, count(*) AS n
                    FROM {source_sql}
                    WHERE session_date >= DATE {sql_string(PHASE25_GATE8_DEVELOPMENT_START.isoformat())}
                      AND session_date <= DATE {sql_string(PHASE25_GATE8_DEVELOPMENT_END.isoformat())}
                    GROUP BY 1,2,3 HAVING count(*) > 1
                )
                """
            ).fetchone()[0]
        )
        if duplicate_source:
            raise Phase25Gate8Error("accepted research source has duplicate development identity/session rows")
        route_rows = int(con.execute("SELECT count(*) FROM p25_gate8_routes").fetchone()[0])
        matched = int(
            con.execute(
                f"""
                SELECT count(*)
                FROM p25_gate8_routes r
                INNER JOIN {source_sql} s
                  ON CAST(s.session_date AS DATE) = CAST(r.as_of_date AS DATE)
                 AND s.instrument_id = r.instrument_id
                 AND s.symbol = r.ticker
                """
            ).fetchone()[0]
        )
        con.execute(
            f"""
            CREATE TEMP VIEW p25_gate8_joined AS
            SELECT
                s.* EXCLUDE (market_regime_composite),
                CAST(r.market_state AS VARCHAR) AS market_regime_composite,
                CAST(r.ticker_state AS VARCHAR) AS ticker_state,
                CAST(r.as_of_date AS DATE) AS route_date,
                CAST(r.strategy_id AS VARCHAR) AS routed_strategy_id
            FROM p25_gate8_routes r
            INNER JOIN {source_sql} s
              ON CAST(s.session_date AS DATE) = CAST(r.as_of_date AS DATE)
             AND s.instrument_id = r.instrument_id
             AND s.symbol = r.ticker
            """
        )
        return {
            "route_eligible_rows": route_rows,
            "research_source_matched_route_rows": matched,
            "research_source_missing_route_rows": route_rows - matched,
        }

    def _signal_frame(self, con) -> pd.DataFrame:
        selects: list[str] = []
        for strategy in DEFAULT_STRATEGY_REGISTRY.all():
            if not isinstance(strategy, RuleStrategy):
                raise Phase25Gate8Error("Gate8 requires fixed RuleStrategy incumbents")
            sid = strategy.metadata.strategy_id
            sign = 1.0 if strategy.metadata.direction.value == "LONG" else -1.0
            condition = strategy_condition_sql(strategy)
            selects.append(
                f"""
                SELECT
                    {sql_string(PHASE25_GATE8_SIGNAL_CONTRACT_VERSION)} AS contract_version,
                    CAST(session_date AS DATE) AS session_date,
                    instrument_id,
                    symbol AS ticker,
                    {sql_string(sid)} AS strategy_id,
                    {sql_string(strategy.metadata.family.value)} AS strategy_family,
                    {sql_string(strategy.metadata.direction.value)} AS strategy_direction,
                    market_regime_composite AS market_state,
                    ticker_state,
                    CAST(forward_return AS DOUBLE) AS forward_return,
                    CAST(forward_return AS DOUBLE) * {sign:.1f} AS directional_return
                FROM p25_gate8_joined
                WHERE routed_strategy_id = {sql_string(sid)}
                  AND forward_return IS NOT NULL
                  AND isfinite(CAST(forward_return AS DOUBLE))
                  AND {condition}
                """
            )
        frame = con.execute(" UNION ALL ".join(selects) + " ORDER BY session_date, strategy_id, instrument_id").fetch_df()
        if not frame.empty:
            frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.date
        return frame

    def run(self, *, through_date: date) -> dict[str, object]:
        if PHASE25_GATE8_PROVIDER_READS != 0 or PHASE25_GATE8_PROVIDER_WRITES != 0:
            raise Phase25Gate8Error("Gate8 must remain provider-free")
        if not PHASE25_GATE8_STRATEGY_RULE_EVALUATION_ALLOWED or not PHASE25_GATE8_STRATEGY_RETURNS_READ_ALLOWED:
            raise Phase25Gate8Error("Gate8 rule/return research authority is unexpectedly disabled")
        if PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED:
            raise Phase25Gate8Error("Gate8 cannot read protected strategy evidence")
        if PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED:
            raise Phase25Gate8Error("Gate8 cannot replace Phase11 support")
        if PHASE25_GATE8_STRATEGY_RULE_CHANGES_ALLOWED or PHASE25_GATE8_OUTCOME_CHANGES_ALLOWED:
            raise Phase25Gate8Error("Gate8 cannot change strategy rules or outcome definition")
        if not PHASE25_GATE8_BROAD_COMPARATOR_ALLOWED:
            raise Phase25Gate8Error("Gate8 broad comparator is unexpectedly disabled")

        gate7_report_path, gate7_validation_path, routes_path, gate7 = self._gate7_evidence(through_date)
        source = self.source_resolver.resolve()
        con = connect_utc(":memory:")
        try:
            coverage = self._create_joined_view(con, routes_path=routes_path, source_sql=source.source_sql)
            strategy_results: list[dict[str, object]] = []
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                sid = strategy.metadata.strategy_id
                production_source = (
                    f"(SELECT * FROM p25_gate8_joined WHERE routed_strategy_id = {sql_string(sid)})"
                )
                production = self.engine.evaluate_source(
                    con,
                    source_sql=production_source,
                    strategy_id=sid,
                    cost_grid_bps=PHASE25_GATE8_COST_GRID_BPS,
                    start_date=PHASE25_GATE8_DEVELOPMENT_START.isoformat(),
                    end_date=PHASE25_GATE8_DEVELOPMENT_END.isoformat(),
                ).to_dict()
                broad = self.engine.evaluate_source(
                    con,
                    source_sql=source.source_sql,
                    strategy_id=sid,
                    cost_grid_bps=PHASE25_GATE8_COST_GRID_BPS,
                    start_date=PHASE25_GATE8_DEVELOPMENT_START.isoformat(),
                    end_date=PHASE25_GATE8_DEVELOPMENT_END.isoformat(),
                ).to_dict()
                production_mean = _primary_mean(production)
                broad_mean = _primary_mean(broad)
                delta = None if production_mean is None or broad_mean is None else production_mean - broad_mean
                strategy_results.append(
                    {
                        "strategy_id": sid,
                        "family": strategy.metadata.family.value,
                        "direction": strategy.metadata.direction.value,
                        "production_path": production,
                        "broad_comparator": broad,
                        "primary_10bps_mean_delta": delta,
                    }
                )
            signals = self._signal_frame(con)
            fired_candidate_count = int(
                con.execute(
                    """
                    SELECT count(DISTINCT CAST(session_date AS VARCHAR) || ':' || instrument_id)
                    FROM (
                        SELECT session_date, instrument_id FROM phase25_gate8_signals
                    )
                    """
                ).fetchone()[0]
            ) if False else int(signals[["session_date", "instrument_id"]].drop_duplicates().shape[0])
        finally:
            con.close()

        if not signals.empty and max(signals["session_date"]) >= PHASE25_GATE8_PROTECTED_START:
            raise Phase25Gate8Error("Gate8 signal artifact crossed protected start")
        signals_path = self.signals_path(through_date)
        self._write_parquet(self.settings, signals, signals_path)

        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE8_REPORT_CONTRACT_VERSION,
            "phase25_gate8_policy_fingerprint": phase25_gate8_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "development_start": PHASE25_GATE8_DEVELOPMENT_START.isoformat(),
            "development_end": PHASE25_GATE8_DEVELOPMENT_END.isoformat(),
            "protected_start": PHASE25_GATE8_PROTECTED_START.isoformat(),
            "outcome_contract_version": PHASE25_GATE8_OUTCOME_CONTRACT_VERSION,
            "cost_grid_bps": list(PHASE25_GATE8_COST_GRID_BPS),
            "gate7_report_sha256": sha256_file(gate7_report_path),
            "gate7_validation_sha256": sha256_file(gate7_validation_path),
            "gate7_routes_sha256": sha256_file(routes_path),
            "gate7_population_rows": int(gate7["gate6_population_rows"]),
            "gate7_market_compatible_candidates": int(gate7["market_route_compatible_candidates"]),
            "gate7_ticker_compatible_candidates": int(gate7["ticker_route_compatible_candidates"]),
            "gate7_fully_route_eligible_candidates": int(gate7["fully_route_eligible_candidates"]),
            "gate7_eligible_route_decisions": int(gate7["eligible_route_decisions"]),
            "research_source": source.public_dict(),
            "research_source_fingerprint": source.source_fingerprint,
            **coverage,
            "research_source_route_coverage_fraction": (
                1.0 if coverage["route_eligible_rows"] == 0
                else coverage["research_source_matched_route_rows"] / coverage["route_eligible_rows"]
            ),
            "development_rule_fired_signal_rows": int(len(signals)),
            "development_candidates_with_any_rule_fire": fired_candidate_count,
            "strategy_results": strategy_results,
            "signals_sha256": sha256_file(signals_path),
            "provider_reads": PHASE25_GATE8_PROVIDER_READS,
            "provider_writes": PHASE25_GATE8_PROVIDER_WRITES,
            "strategy_rule_evaluation_performed": True,
            "strategy_returns_read": True,
            "protected_evidence_reads": 0,
            "support_replacement_authority": False,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "global_protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "signals_path": str(signals_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
