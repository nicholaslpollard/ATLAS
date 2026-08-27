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
from .phase24_gate2 import SessionSignal, TrancheMetrics, tranche_metrics
from .phase25_gate7 import PHASE25_GATE7_ROUTE_CONTRACT_VERSION, Phase25Gate7RouteContextReplay
from .phase25_gate9 import Phase25Gate9Robustness
from .phase25_gate9_validation import Phase25Gate9IndependentValidator
from .phase25_gate8_policy import (
    PHASE25_GATE10_CONFIDENCE,
    PHASE25_GATE10_FINALISTS_ONLY,
    PHASE25_GATE10_FOLDS,
    PHASE25_GATE10_MIN_POSITIVE_FOLDS,
    PHASE25_GATE10_MIN_RAW_ROWS,
    PHASE25_GATE10_MIN_SIGNAL_SESSIONS,
    PHASE25_GATE10_PROTECTED_END,
    PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
    PHASE25_GATE10_PROTECTED_START,
    PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS,
    PHASE25_GATE9_MAX_SINGLE_SESSION_ROW_FRACTION,
    phase25_gate10_policy_fingerprint,
)
from .strategy_evaluation import strategy_condition_sql


PHASE25_GATE10_REPORT_CONTRACT_VERSION = (
    "phase25-gate10-report-v1-finalists-only-protected-confirmation"
)
PHASE25_GATE10_SIGNAL_CONTRACT_VERSION = (
    "phase25-gate10-signals-v1-protected-finalist-production-path"
)


class Phase25Gate10Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate10Error(f"missing Gate10 prerequisite: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate10Error(f"invalid Gate10 prerequisite JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate10Error("Gate10 prerequisite must be an object")
    return value


def protected_checks(metrics: TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE25_GATE10_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE25_GATE10_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE25_GATE10_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(metrics.primary_mean_return is not None and metrics.primary_mean_return > 0),
        "primary_median_positive": bool(metrics.primary_median_return is not None and metrics.primary_median_return > 0),
        "positive_rate_half": bool(metrics.primary_positive_rate is not None and metrics.primary_positive_rate >= 0.5),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(metrics.stress_mean_return is not None and metrics.stress_mean_return > 0),
        "session_concentration": bool(metrics.max_single_session_row_fraction is not None and metrics.max_single_session_row_fraction <= PHASE25_GATE9_MAX_SINGLE_SESSION_ROW_FRACTION),
    }


class Phase25Gate10ProtectedConfirmation:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate10"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "protected_confirmation.json"

    def signals_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "protected_signals.parquet"

    @staticmethod
    def _write_parquet(settings: AtlasSettings, frame: pd.DataFrame, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("phase25_gate10_frame", frame)
            compression = settings.data.parquet.compression.upper()
            row_group_size = int(settings.data.parquet.row_group_size)
            con.execute(
                f"COPY (SELECT * FROM phase25_gate10_frame ORDER BY session_date, strategy_id, instrument_id) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})"
            )
            promote(temp, target)
        finally:
            con.close()

    def _build_signals(self, *, through_date: date, finalist_ids: tuple[str, ...]) -> tuple[pd.DataFrame, dict[str, int], str]:
        gate7 = Phase25Gate7RouteContextReplay(self.settings)
        routes_path = gate7.routes_path(through_date)
        if not routes_path.is_file():
            raise Phase25Gate10Error("Gate7 routes missing for protected confirmation")
        source = self.source_resolver.resolve()
        con = connect_utc(":memory:")
        try:
            finalist_sql = ",".join(sql_string(item) for item in finalist_ids)
            con.execute(
                f"""
                CREATE TEMP VIEW p25_gate10_routes AS
                SELECT * FROM read_parquet({sql_string(routes_path)})
                WHERE contract_version={sql_string(PHASE25_GATE7_ROUTE_CONTRACT_VERSION)}
                  AND eligible=TRUE
                  AND strategy_id IN ({finalist_sql})
                  AND as_of_date >= DATE {sql_string(PHASE25_GATE10_PROTECTED_START.isoformat())}
                  AND as_of_date <= DATE {sql_string(PHASE25_GATE10_PROTECTED_END.isoformat())}
                """
            )
            route_rows = int(con.execute("SELECT count(*) FROM p25_gate10_routes").fetchone()[0])
            matched_rows = int(
                con.execute(
                    f"""
                    SELECT count(*) FROM p25_gate10_routes r
                    INNER JOIN {source.source_sql} s
                      ON CAST(s.session_date AS DATE)=CAST(r.as_of_date AS DATE)
                     AND s.instrument_id=r.instrument_id
                     AND s.symbol=r.ticker
                    """
                ).fetchone()[0]
            )
            con.execute(
                f"""
                CREATE TEMP VIEW p25_gate10_joined AS
                SELECT
                    s.* EXCLUDE (market_regime_composite),
                    CAST(r.market_state AS VARCHAR) AS market_regime_composite,
                    CAST(r.ticker_state AS VARCHAR) AS ticker_state,
                    CAST(r.strategy_id AS VARCHAR) AS routed_strategy_id
                FROM p25_gate10_routes r
                INNER JOIN {source.source_sql} s
                  ON CAST(s.session_date AS DATE)=CAST(r.as_of_date AS DATE)
                 AND s.instrument_id=r.instrument_id
                 AND s.symbol=r.ticker
                """
            )
            selects: list[str] = []
            for sid in finalist_ids:
                strategy = DEFAULT_STRATEGY_REGISTRY.get(sid)
                if not isinstance(strategy, RuleStrategy):
                    raise Phase25Gate10Error("Gate10 finalist is not a RuleStrategy")
                sign = 1.0 if strategy.metadata.direction.value == "LONG" else -1.0
                condition = strategy_condition_sql(strategy)
                selects.append(
                    f"""
                    SELECT
                        {sql_string(PHASE25_GATE10_SIGNAL_CONTRACT_VERSION)} AS contract_version,
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
                    FROM p25_gate10_joined
                    WHERE routed_strategy_id={sql_string(sid)}
                      AND forward_return IS NOT NULL
                      AND isfinite(CAST(forward_return AS DOUBLE))
                      AND {condition}
                    """
                )
            frame = con.execute(" UNION ALL ".join(selects) + " ORDER BY session_date, strategy_id, instrument_id").fetch_df()
        finally:
            con.close()
        if not frame.empty:
            frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.date
        return frame, {
            "protected_route_eligible_rows": route_rows,
            "protected_research_source_matched_route_rows": matched_rows,
            "protected_research_source_missing_route_rows": route_rows - matched_rows,
        }, source.source_fingerprint

    @staticmethod
    def _session_signals(path: Path, strategy_id: str) -> tuple[SessionSignal, ...]:
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT CAST(session_date AS DATE), min(market_state), max(market_state), count(*), avg(directional_return)
                FROM read_parquet({sql_string(path)})
                WHERE strategy_id={sql_string(strategy_id)}
                GROUP BY 1 ORDER BY 1
                """
            ).fetchall()
        finally:
            con.close()
        output: list[SessionSignal] = []
        for session_date, min_regime, max_regime, raw_rows, gross_mean in rows:
            if str(min_regime) != str(max_regime):
                raise Phase25Gate10Error(f"protected market state inconsistent: {session_date}")
            output.append(SessionSignal(session_date, str(min_regime), int(raw_rows), float(gross_mean)))
        return tuple(output)

    def run(self, *, through_date: date) -> dict[str, object]:
        if not PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED or not PHASE25_GATE10_FINALISTS_ONLY:
            raise Phase25Gate10Error("Gate10 protected-finalist contract changed")
        if PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED:
            raise Phase25Gate10Error("Gate10 may not replace support")
        gate9 = Phase25Gate9Robustness(self.settings)
        gate9_report_path = gate9.report_path(through_date)
        gate9_validation_path = Phase25Gate9IndependentValidator(self.settings).report_path(through_date)
        gate9_report = _read_json(gate9_report_path)
        gate9_validation = _read_json(gate9_validation_path)
        if gate9_report.get("pass") is not True or gate9_validation.get("pass") is not True:
            raise Phase25Gate10Error("Gate10 requires accepted Gate9 evidence")
        finalist_ids = tuple(sorted(str(item) for item in gate9_report.get("finalist_strategy_ids", [])))

        report_path = self.report_path(through_date)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        if not finalist_ids:
            if not PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS:
                raise Phase25Gate10Error("zero-finalist protected-read policy changed")
            report = {
                "contract_version": PHASE25_GATE10_REPORT_CONTRACT_VERSION,
                "phase25_gate10_policy_fingerprint": phase25_gate10_policy_fingerprint(),
                "through_date": through_date.isoformat(),
                "gate9_report_sha256": sha256_file(gate9_report_path),
                "gate9_validation_sha256": sha256_file(gate9_validation_path),
                "gate9_finalist_lock_sha256": sha256_file(gate9.finalist_lock_path(through_date)),
                "finalist_strategy_ids": [],
                "confirmed_strategy_ids": [],
                "protected_results": [],
                "protected_evidence_reads": 0,
                "protected_evidence_fresh": PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
                "disposition": "SKIPPED_ZERO_FINALISTS",
                "support_replacement_authority": False,
                "phase11_support_writes": 0,
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "report_path": str(report_path.resolve()),
                "pass": True,
            }
            atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
            return report

        signals, coverage, source_fingerprint = self._build_signals(
            through_date=through_date,
            finalist_ids=finalist_ids,
        )
        signals_path = self.signals_path(through_date)
        self._write_parquet(self.settings, signals, signals_path)
        results: list[dict[str, object]] = []
        confirmed: list[str] = []
        for sid in finalist_ids:
            metrics = tranche_metrics(
                self._session_signals(signals_path, sid),
                confidence=PHASE25_GATE10_CONFIDENCE,
                folds=PHASE25_GATE10_FOLDS,
                label=f"phase25-protected:{sid}",
            )
            checks = protected_checks(metrics)
            passed = all(checks.values())
            results.append(
                {
                    "strategy_id": sid,
                    "metrics": metrics.to_dict(),
                    "checks": checks,
                    "confirmed": passed,
                }
            )
            if passed:
                confirmed.append(sid)

        report = {
            "contract_version": PHASE25_GATE10_REPORT_CONTRACT_VERSION,
            "phase25_gate10_policy_fingerprint": phase25_gate10_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "gate9_report_sha256": sha256_file(gate9_report_path),
            "gate9_validation_sha256": sha256_file(gate9_validation_path),
            "gate9_finalist_lock_sha256": sha256_file(gate9.finalist_lock_path(through_date)),
            "protected_start": PHASE25_GATE10_PROTECTED_START.isoformat(),
            "protected_end": PHASE25_GATE10_PROTECTED_END.isoformat(),
            "finalist_strategy_ids": list(finalist_ids),
            "confirmed_strategy_ids": sorted(confirmed),
            "protected_results": results,
            **coverage,
            "research_source_fingerprint": source_fingerprint,
            "signals_sha256": sha256_file(signals_path),
            "protected_evidence_reads": 1,
            "protected_evidence_fresh": PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
            "disposition": "PROTECTED_CONFIRMATION_COMPLETED",
            "support_replacement_authority": False,
            "phase11_support_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "signals_path": str(signals_path.resolve()),
            "pass": True,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return report
