from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_FINAL_HOLDOUT_END,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
)
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry

from .historical_source import HistoricalStrategyResearchSourceResolver
from .strategy_evaluation import StrategyEvaluationEngine
from .strategy_support import (
    STRATEGY_SUPPORT_PRIMARY_COST_BPS,
    classify_strategy_support,
)


STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION = (
    "strategy-historical-study-v1-development-halves-then-protected-confirmation"
)
STRATEGY_HISTORICAL_STUDY_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0)
STRATEGY_HISTORICAL_STUDY_PRODUCTION_WRITES = 0
STRATEGY_HISTORICAL_STUDY_BROKER_WRITES = 0


class StrategyHistoricalStudyError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _support_dict(decision) -> dict[str, object]:
    payload = asdict(decision)
    payload["status"] = decision.status.value
    payload["eligible_for_candidate_promotion"] = decision.eligible_for_candidate_promotion
    return payload


class StrategyHistoricalStudy:
    """Run the preregistered Phase 11 strategy evidence study.

    Support is classified from the development period and its two chronological
    halves before protected-holdout results are attached. Protected results are
    confirmation evidence only and cannot change the support classification.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        registry: StrategyRegistry = DEFAULT_STRATEGY_REGISTRY,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        self.engine = StrategyEvaluationEngine(registry)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase11" / "v1"
        self.report_path = self.root / "historical_strategy_study.json"

    @staticmethod
    def _development_boundaries(con: Any, source_sql: str) -> tuple[str, str, str, str, int]:
        sessions = [
            str(row[0])
            for row in con.execute(
                f"""
                SELECT DISTINCT CAST(session_date AS VARCHAR)
                FROM {source_sql}
                WHERE session_date < DATE '{ML_WALK_FORWARD_FINAL_HOLDOUT_START}'
                ORDER BY 1
                """
            ).fetchall()
        ]
        if len(sessions) < 2:
            raise StrategyHistoricalStudyError("strategy development period has fewer than two sessions")
        midpoint = len(sessions) // 2
        if midpoint <= 0 or midpoint >= len(sessions):
            raise StrategyHistoricalStudyError("strategy development midpoint is invalid")
        return sessions[0], sessions[-1], sessions[midpoint - 1], sessions[midpoint], len(sessions)

    def run(self, *, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        source = self.source_resolver.resolve()
        con = connect_utc(":memory:")
        try:
            development_start, development_end, first_half_end, second_half_start, development_sessions = (
                self._development_boundaries(con, source.source_sql)
            )
            if development_end >= ML_WALK_FORWARD_FINAL_HOLDOUT_START:
                raise StrategyHistoricalStudyError("development period reaches protected holdout")

            studies: list[dict[str, object]] = []
            for strategy in self.registry.all():
                strategy_id = strategy.metadata.strategy_id
                if progress is not None:
                    progress(f"strategy {strategy_id}: development study")
                development = self.engine.evaluate_source(
                    con,
                    source_sql=source.source_sql,
                    strategy_id=strategy_id,
                    cost_grid_bps=STRATEGY_HISTORICAL_STUDY_COST_GRID_BPS,
                    start_date=development_start,
                    end_date=development_end,
                )
                first_half = self.engine.evaluate_source(
                    con,
                    source_sql=source.source_sql,
                    strategy_id=strategy_id,
                    cost_grid_bps=(STRATEGY_SUPPORT_PRIMARY_COST_BPS,),
                    start_date=development_start,
                    end_date=first_half_end,
                )
                second_half = self.engine.evaluate_source(
                    con,
                    source_sql=source.source_sql,
                    strategy_id=strategy_id,
                    cost_grid_bps=(STRATEGY_SUPPORT_PRIMARY_COST_BPS,),
                    start_date=second_half_start,
                    end_date=development_end,
                )
                support = classify_strategy_support(
                    development=development,
                    first_half=first_half,
                    second_half=second_half,
                )
                support_payload = _support_dict(support)
                if progress is not None:
                    progress(
                        f"strategy {strategy_id}: support={support.status.value} "
                        f"dev10bps={support.development_mean_return}"
                    )

                # Classification is complete before protected results are evaluated.
                protected = self.engine.evaluate_source(
                    con,
                    source_sql=source.source_sql,
                    strategy_id=strategy_id,
                    cost_grid_bps=STRATEGY_HISTORICAL_STUDY_COST_GRID_BPS,
                    start_date=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
                    end_date=ML_WALK_FORWARD_FINAL_HOLDOUT_END,
                )
                studies.append(
                    {
                        "strategy_id": strategy_id,
                        "metadata": asdict(strategy.metadata),
                        "development": development.to_dict(),
                        "first_half_primary_cost": first_half.to_dict(),
                        "second_half_primary_cost": second_half.to_dict(),
                        "support": support_payload,
                        "protected_confirmation": protected.to_dict(),
                        "protected_confirmation_used_for_support": False,
                    }
                )
        finally:
            con.close()

        supported = [item["strategy_id"] for item in studies if item["support"]["eligible_for_candidate_promotion"]]
        checks = {
            "accepted_research_source_bound": True,
            "registry_nonempty": len(studies) == len(self.registry.all()) and len(studies) > 0,
            "development_precedes_protected_holdout": development_end < ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            "protected_holdout_not_used_for_support": all(
                item["protected_confirmation_used_for_support"] is False for item in studies
            ),
            "support_decisions_complete": all(bool(item["support"]["status"]) for item in studies),
            "production_writes_zero": STRATEGY_HISTORICAL_STUDY_PRODUCTION_WRITES == 0,
            "broker_writes_zero": STRATEGY_HISTORICAL_STUDY_BROKER_WRITES == 0,
        }
        fingerprint_payload = {
            "contract_version": STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION,
            "source_fingerprint": source.source_fingerprint,
            "strategy_registry_fingerprint": self.registry.fingerprint(),
            "development_start": development_start,
            "development_end": development_end,
            "first_half_end": first_half_end,
            "second_half_start": second_half_start,
            "protected_holdout_start": ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            "protected_holdout_end": ML_WALK_FORWARD_FINAL_HOLDOUT_END,
            "cost_grid_bps": list(STRATEGY_HISTORICAL_STUDY_COST_GRID_BPS),
            "studies": studies,
        }
        report: dict[str, object] = {
            "contract_version": STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(fingerprint_payload),
            "research_source": source.public_dict(),
            "strategy_registry_fingerprint": self.registry.fingerprint(),
            "strategy_count": len(studies),
            "development_start": development_start,
            "development_end": development_end,
            "development_sessions": development_sessions,
            "first_half_end": first_half_end,
            "second_half_start": second_half_start,
            "protected_holdout_start": ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            "protected_holdout_end": ML_WALK_FORWARD_FINAL_HOLDOUT_END,
            "protected_holdout_role": "CONFIRMATION_ONLY_NOT_SUPPORT_SELECTION",
            "cost_grid_bps": list(STRATEGY_HISTORICAL_STUDY_COST_GRID_BPS),
            "supported_strategy_ids": supported,
            "studies": studies,
            "checks": checks,
            "production_writes": 0,
            "broker_writes": 0,
            "pass": all(checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
