from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from packages.data.sql import sql_string
from packages.schemas.strategy import StrategyDirection
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry
from packages.strategies.rules import Comparison, FeatureCondition, RuleStrategy

from .outcomes import DEFAULT_COST_GRID_BPS


STRATEGY_EVALUATION_CONTRACT_VERSION = (
    "strategy-evaluation-v2-identity-safe-bounded-three-session-signal-study"
)
STRATEGY_SOURCE_COLUMN_ALIASES = {"close": "observation_close"}


@dataclass(frozen=True, slots=True)
class StrategyEvaluationMetrics:
    rows: int
    mean_return: float | None
    median_return: float | None
    positive_rate: float | None
    stddev_return: float | None
    p10_return: float | None
    p25_return: float | None
    p75_return: float | None
    p90_return: float | None
    worst_return: float | None
    best_return: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StrategyEvaluationSummary:
    contract_version: str
    strategy_id: str
    direction: str
    evaluation_start: str | None
    evaluation_end: str | None
    source_rows: int
    fired_rows: int
    routed_rows: int
    cost_grid_bps: tuple[float, ...]
    aggregate_by_cost_bps: dict[str, StrategyEvaluationMetrics]
    by_year: dict[str, StrategyEvaluationMetrics]
    by_market_regime: dict[str, StrategyEvaluationMetrics]

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "strategy_id": self.strategy_id,
            "direction": self.direction,
            "evaluation_start": self.evaluation_start,
            "evaluation_end": self.evaluation_end,
            "source_rows": self.source_rows,
            "fired_rows": self.fired_rows,
            "routed_rows": self.routed_rows,
            "cost_grid_bps": list(self.cost_grid_bps),
            "aggregate_by_cost_bps": {
                key: value.to_dict() for key, value in self.aggregate_by_cost_bps.items()
            },
            "by_year": {key: value.to_dict() for key, value in self.by_year.items()},
            "by_market_regime": {
                key: value.to_dict() for key, value in self.by_market_regime.items()
            },
        }


def _identifier(name: str) -> str:
    if not name or not all(ch.isalnum() or ch == "_" for ch in name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return f'"{name}"'


def _source_identifier(name: str) -> str:
    return _identifier(STRATEGY_SOURCE_COLUMN_ALIASES.get(name, name))


def condition_sql(condition: FeatureCondition) -> str:
    left = _source_identifier(condition.left)
    operator = {
        Comparison.GT: ">",
        Comparison.GE: ">=",
        Comparison.LT: "<",
        Comparison.LE: "<=",
    }[condition.comparison]
    if condition.right_feature is not None:
        right = _source_identifier(condition.right_feature)
        right_guard = f" AND {right} IS NOT NULL AND isfinite(CAST({right} AS DOUBLE))"
    else:
        right = format(float(condition.right_value), ".17g")
        right_guard = ""
    return (
        f"({left} IS NOT NULL AND isfinite(CAST({left} AS DOUBLE))"
        f"{right_guard} AND {left} {operator} {right})"
    )


def strategy_condition_sql(strategy: RuleStrategy) -> str:
    return " AND ".join(condition_sql(condition) for condition in strategy.conditions)


def historical_market_route_sql(direction: StrategyDirection, field: str = "market_regime_composite") -> str:
    column = _identifier(field)
    allowed = ("BULL", "STRONG_BULL", "MIXED") if direction == StrategyDirection.LONG else (
        "BEAR",
        "STRONG_BEAR",
        "MIXED",
    )
    values = ", ".join(sql_string(value) for value in allowed)
    # Unavailable historical context stays unavailable rather than being fabricated.
    return f"({column} IS NULL OR {column} IN ({values}))"


def _date_clause(start_date: str | None, end_date: str | None) -> str:
    clauses: list[str] = []
    if start_date is not None:
        clauses.append(f"session_date >= DATE {sql_string(start_date)}")
    if end_date is not None:
        clauses.append(f"session_date <= DATE {sql_string(end_date)}")
    return "" if not clauses else " AND " + " AND ".join(clauses)


def _metrics_from_row(row: tuple[Any, ...]) -> StrategyEvaluationMetrics:
    return StrategyEvaluationMetrics(
        rows=int(row[0]),
        mean_return=None if row[1] is None else float(row[1]),
        median_return=None if row[2] is None else float(row[2]),
        positive_rate=None if row[3] is None else float(row[3]),
        stddev_return=None if row[4] is None else float(row[4]),
        p10_return=None if row[5] is None else float(row[5]),
        p25_return=None if row[6] is None else float(row[6]),
        p75_return=None if row[7] is None else float(row[7]),
        p90_return=None if row[8] is None else float(row[8]),
        worst_return=None if row[9] is None else float(row[9]),
        best_return=None if row[10] is None else float(row[10]),
    )


def _metric_select(return_expression: str) -> str:
    return f"""
        count(*) AS rows,
        avg({return_expression}) AS mean_return,
        median({return_expression}) AS median_return,
        avg(CASE WHEN {return_expression} > 0 THEN 1.0 ELSE 0.0 END) AS positive_rate,
        stddev_pop({return_expression}) AS stddev_return,
        quantile_cont({return_expression}, 0.10) AS p10_return,
        quantile_cont({return_expression}, 0.25) AS p25_return,
        quantile_cont({return_expression}, 0.75) AS p75_return,
        quantile_cont({return_expression}, 0.90) AS p90_return,
        min({return_expression}) AS worst_return,
        max({return_expression}) AS best_return
    """


class StrategyEvaluationEngine:
    """DuckDB signal-study evaluator over identity-safe feature/outcome evidence.

    This studies setup-conditioned forward returns only. It never constructs positions,
    assumes fills, computes trade geometry, or emits broker instructions.
    """

    def __init__(self, registry: StrategyRegistry = DEFAULT_STRATEGY_REGISTRY) -> None:
        self.registry = registry

    def evaluate_source(
        self,
        con: Any,
        *,
        source_sql: str,
        strategy_id: str,
        cost_grid_bps: tuple[float, ...] = DEFAULT_COST_GRID_BPS,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> StrategyEvaluationSummary:
        strategy = self.registry.get(strategy_id)
        if not isinstance(strategy, RuleStrategy):
            raise TypeError("historical evaluation currently requires RuleStrategy implementations")
        if not cost_grid_bps or any(float(value) < 0.0 for value in cost_grid_bps):
            raise ValueError("cost_grid_bps must contain non-negative values")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date cannot be after end_date")

        condition = strategy_condition_sql(strategy)
        route = historical_market_route_sql(strategy.metadata.direction)
        bounded = _date_clause(start_date, end_date)
        direction_sign = 1.0 if strategy.metadata.direction == StrategyDirection.LONG else -1.0
        directional = f"(CAST(forward_return AS DOUBLE) * {direction_sign:.1f})"

        counts = con.execute(
            f"""
            SELECT
                count(*) AS source_rows,
                count(*) FILTER (WHERE {condition}) AS fired_rows,
                count(*) FILTER (WHERE {condition} AND {route}) AS routed_rows
            FROM {source_sql}
            WHERE forward_return IS NOT NULL
              AND isfinite(CAST(forward_return AS DOUBLE))
              {bounded}
            """
        ).fetchone()

        aggregate: dict[str, StrategyEvaluationMetrics] = {}
        for cost_bps in cost_grid_bps:
            cost = float(cost_bps) / 10_000.0
            expression = f"({directional} - {cost:.17g})"
            row = con.execute(
                f"""
                SELECT {_metric_select(expression)}
                FROM {source_sql}
                WHERE forward_return IS NOT NULL
                  AND isfinite(CAST(forward_return AS DOUBLE))
                  AND {condition}
                  AND {route}
                  {bounded}
                """
            ).fetchone()
            aggregate[format(float(cost_bps), "g")] = _metrics_from_row(row)

        by_year_rows = con.execute(
            f"""
            SELECT
                CAST(year(session_date) AS VARCHAR) AS slice_key,
                {_metric_select(directional)}
            FROM {source_sql}
            WHERE forward_return IS NOT NULL
              AND isfinite(CAST(forward_return AS DOUBLE))
              AND {condition}
              AND {route}
              {bounded}
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        by_year = {str(row[0]): _metrics_from_row(tuple(row[1:])) for row in by_year_rows}

        by_regime_rows = con.execute(
            f"""
            SELECT
                coalesce(CAST(market_regime_composite AS VARCHAR), 'UNAVAILABLE') AS slice_key,
                {_metric_select(directional)}
            FROM {source_sql}
            WHERE forward_return IS NOT NULL
              AND isfinite(CAST(forward_return AS DOUBLE))
              AND {condition}
              AND {route}
              {bounded}
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        by_regime = {str(row[0]): _metrics_from_row(tuple(row[1:])) for row in by_regime_rows}

        return StrategyEvaluationSummary(
            contract_version=STRATEGY_EVALUATION_CONTRACT_VERSION,
            strategy_id=strategy.metadata.strategy_id,
            direction=strategy.metadata.direction.value,
            evaluation_start=start_date,
            evaluation_end=end_date,
            source_rows=int(counts[0]),
            fired_rows=int(counts[1]),
            routed_rows=int(counts[2]),
            cost_grid_bps=tuple(float(value) for value in cost_grid_bps),
            aggregate_by_cost_bps=aggregate,
            by_year=by_year,
            by_market_regime=by_regime,
        )
