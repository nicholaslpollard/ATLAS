from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths

from .ticker_history_probe import (
    AUTHORITATIVE_CURRENT_INTERVAL,
    CURRENT_ALIAS_NO_CONFLICT,
    TickerHistoryProbe,
    history_status,
    operational_history_depth,
)


TICKER_RISK_PROBE_CONTRACT_VERSION = (
    "ticker-risk-probe-v1-safe-self-relative-prior-only-lookback-grid"
)
TICKER_RISK_LOOKBACK_WINDOWS = (20, 60, 126, 252)
TICKER_RISK_REFERENCE_WINDOW = 252
TICKER_RISK_METRICS = (
    "natr_14",
    "realized_volatility_20",
    "directional_efficiency_20",
)
RISK_STATE_ORDER = ("CALM", "NORMAL", "ELEVATED", "STRESSED")
EFFICIENCY_STATE_ORDER = ("LOW", "NORMAL", "HIGH")


@dataclass(frozen=True, slots=True)
class TickerRiskProbeReport:
    contract_version: str
    generated_at_utc: str
    as_of_date: str
    wall_seconds: float
    probe_status: str
    history_safety_note: str
    threshold_note: str
    route_population_count: int
    identity_safe_history_instrument_count: int
    identity_blocked_history_instrument_count: int
    current_metric_instrument_count: int
    missing_current_metric_instrument_count: int
    lookback_windows: tuple[int, ...]
    coverage_by_window: dict[str, int]
    insufficient_for_shortest_window_count: int
    candidate_windows: dict[str, dict[str, object]]
    report_path: str


def self_relative_volatility_state(
    *,
    natr_value: float,
    realized_volatility_value: float,
    natr_p25: float,
    natr_p75: float,
    natr_p90: float,
    realized_p25: float,
    realized_p75: float,
    realized_p90: float,
) -> str:
    if natr_value >= natr_p90 or realized_volatility_value >= realized_p90:
        return "STRESSED"
    if natr_value >= natr_p75 or realized_volatility_value >= realized_p75:
        return "ELEVATED"
    if natr_value <= natr_p25 and realized_volatility_value <= realized_p25:
        return "CALM"
    return "NORMAL"


def self_relative_efficiency_state(*, value: float, p25: float, p75: float) -> str:
    if value <= p25:
        return "LOW"
    if value >= p75:
        return "HIGH"
    return "NORMAL"


def ordinal_agreement(
    shorter: pd.Series,
    reference: pd.Series,
    order: tuple[str, ...],
) -> dict[str, float | int | None]:
    pairs = pd.DataFrame({"shorter": shorter, "reference": reference}).dropna()
    if pairs.empty:
        return {
            "comparison_count": 0,
            "exact_agreement_rate": None,
            "within_one_level_rate": None,
            "two_or_more_level_mismatch_count": 0,
            "two_or_more_level_mismatch_rate": None,
            "max_level_distance": None,
        }
    ranking = {state: index for index, state in enumerate(order)}
    distances = [
        abs(ranking[str(left)] - ranking[str(right)])
        for left, right in zip(pairs["shorter"], pairs["reference"], strict=True)
    ]
    count = len(distances)
    exact = sum(distance == 0 for distance in distances)
    within_one = sum(distance <= 1 for distance in distances)
    material = sum(distance >= 2 for distance in distances)
    return {
        "comparison_count": count,
        "exact_agreement_rate": exact / count,
        "within_one_level_rate": within_one / count,
        "two_or_more_level_mismatch_count": material,
        "two_or_more_level_mismatch_rate": material / count,
        "max_level_distance": max(distances),
    }


class TickerRiskProbe:
    """Measure prior-only self-relative ticker risk/efficiency lookback candidates."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "ticker_risk_probe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def _identity_safe_population(self, as_of_date: date) -> tuple[pd.DataFrame, int]:
        history_probe = TickerHistoryProbe(self.settings)
        paths = history_probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            routes = history_probe._prepare_population(con, paths)
            history_probe._prepare_identity(con, paths, as_of_date)
            frame = history_probe._history_depth_frame(con, as_of_date)
        finally:
            con.close()

        statuses: list[str] = []
        depths: list[int] = []
        starts: list[date | None] = []
        for _, row in frame.iterrows():
            status = history_status(
                alias_count=int(row["alias_count"]),
                reuse_identity_count=int(row["reuse_identity_count"]),
                authoritative_current_interval_count=int(row["authoritative_current_interval_count"]),
            )
            depth = operational_history_depth(
                status=status,
                raw_current_alias_depth=int(row["raw_current_alias_depth"]),
                authoritative_interval_depth=int(row["authoritative_interval_depth"]),
            )
            statuses.append(status)
            depths.append(depth)
            starts.append(
                pd.Timestamp(row["current_interval_from"]).date()
                if status == AUTHORITATIVE_CURRENT_INTERVAL and pd.notna(row["current_interval_from"])
                else None
            )

        frame = frame.copy()
        frame["history_status"] = statuses
        frame["operational_depth"] = depths
        frame["safe_start_date"] = starts
        safe = frame.loc[
            frame["history_status"].isin({CURRENT_ALIAS_NO_CONFLICT, AUTHORITATIVE_CURRENT_INTERVAL}),
            ["instrument_id", "ticker", "history_status", "operational_depth", "safe_start_date"],
        ].copy()
        safe["safe_start_date"] = pd.to_datetime(safe["safe_start_date"]).dt.date
        return safe, int(routes["population"])

    def _current_quantile_frame(self, population: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
        if population.empty:
            return pd.DataFrame()
        registered = population.copy()
        registered["safe_start_date"] = registered["safe_start_date"].where(
            registered["safe_start_date"].notna(), date(1900, 1, 1)
        )
        con = connect_utc(":memory:")
        try:
            con.register("atlas_ticker_risk_population", registered)
            feature_glob = self._safe(self.paths.feature_glob(Timeframe.DAY_1))
            as_of = as_of_date.isoformat()
            window_columns: list[str] = []
            for window in TICKER_RISK_LOOKBACK_WINDOWS:
                bounds = f"ROWS BETWEEN {window} PRECEDING AND 1 PRECEDING"
                window_columns.extend(
                    [
                        f"count(*) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS prior_count_{window}",
                        f"quantile_cont(natr_14, 0.25) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS natr_p25_{window}",
                        f"quantile_cont(natr_14, 0.75) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS natr_p75_{window}",
                        f"quantile_cont(natr_14, 0.90) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS natr_p90_{window}",
                        f"quantile_cont(realized_volatility_20, 0.25) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS rv_p25_{window}",
                        f"quantile_cont(realized_volatility_20, 0.75) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS rv_p75_{window}",
                        f"quantile_cont(realized_volatility_20, 0.90) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS rv_p90_{window}",
                        f"quantile_cont(directional_efficiency_20, 0.25) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS eff_p25_{window}",
                        f"quantile_cont(directional_efficiency_20, 0.75) OVER (PARTITION BY instrument_id ORDER BY trading_date {bounds}) AS eff_p75_{window}",
                    ]
                )
            columns_sql = ",\n                    ".join(window_columns)
            query = f"""
            WITH history AS (
                SELECT * EXCLUDE (rn_desc) FROM (
                    SELECT
                        p.instrument_id,
                        p.ticker,
                        CAST(f.timestamp_utc AS DATE) AS trading_date,
                        f.natr_14,
                        f.realized_volatility_20,
                        f.directional_efficiency_20,
                        row_number() OVER (
                            PARTITION BY p.instrument_id ORDER BY f.timestamp_utc DESC
                        ) AS rn_desc
                    FROM read_parquet('{feature_glob}', union_by_name=true, hive_partitioning=false) f
                    INNER JOIN atlas_ticker_risk_population p ON p.ticker = f.symbol
                    WHERE CAST(f.timestamp_utc AS DATE) <= DATE '{as_of}'
                      AND CAST(f.timestamp_utc AS DATE) >= p.safe_start_date
                      AND f.natr_14 IS NOT NULL AND isfinite(f.natr_14)
                      AND f.realized_volatility_20 IS NOT NULL AND isfinite(f.realized_volatility_20)
                      AND f.directional_efficiency_20 IS NOT NULL AND isfinite(f.directional_efficiency_20)
                )
                WHERE rn_desc <= {TICKER_RISK_REFERENCE_WINDOW + 1}
            ), scored AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY instrument_id ORDER BY trading_date DESC
                    ) AS current_rank,
                    {columns_sql}
                FROM history
            )
            SELECT *
            FROM scored
            WHERE current_rank = 1
              AND trading_date = DATE '{as_of}'
            ORDER BY instrument_id
            """
            return con.execute(query).fetch_df()
        finally:
            con.close()

    @staticmethod
    def _classify_window(frame: pd.DataFrame, window: int) -> tuple[pd.Series, pd.Series]:
        risk = pd.Series(pd.NA, index=frame.index, dtype="object")
        efficiency = pd.Series(pd.NA, index=frame.index, dtype="object")
        eligible = pd.to_numeric(frame[f"prior_count_{window}"], errors="coerce").fillna(0) >= window
        for index, row in frame.loc[eligible].iterrows():
            risk.at[index] = self_relative_volatility_state(
                natr_value=float(row["natr_14"]),
                realized_volatility_value=float(row["realized_volatility_20"]),
                natr_p25=float(row[f"natr_p25_{window}"]),
                natr_p75=float(row[f"natr_p75_{window}"]),
                natr_p90=float(row[f"natr_p90_{window}"]),
                realized_p25=float(row[f"rv_p25_{window}"]),
                realized_p75=float(row[f"rv_p75_{window}"]),
                realized_p90=float(row[f"rv_p90_{window}"]),
            )
            efficiency.at[index] = self_relative_efficiency_state(
                value=float(row["directional_efficiency_20"]),
                p25=float(row[f"eff_p25_{window}"]),
                p75=float(row[f"eff_p75_{window}"]),
            )
        return risk, efficiency

    def run(self, as_of_date: date) -> TickerRiskProbeReport:
        started = perf_counter()
        population, route_population = self._identity_safe_population(as_of_date)
        frame = self._current_quantile_frame(population, as_of_date)
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        risk_states: dict[int, pd.Series] = {}
        efficiency_states: dict[int, pd.Series] = {}
        coverage: dict[str, int] = {}
        for window in TICKER_RISK_LOOKBACK_WINDOWS:
            risk, efficiency = self._classify_window(frame, window)
            risk_states[window] = risk
            efficiency_states[window] = efficiency
            coverage[str(window)] = int(risk.notna().sum())

        reference_risk = risk_states[TICKER_RISK_REFERENCE_WINDOW]
        reference_efficiency = efficiency_states[TICKER_RISK_REFERENCE_WINDOW]
        candidates: dict[str, dict[str, object]] = {}
        for window in TICKER_RISK_LOOKBACK_WINDOWS:
            risk = risk_states[window]
            efficiency = efficiency_states[window]
            eligible = risk.notna()
            risk_counts = Counter(risk.loc[eligible].astype(str).tolist())
            efficiency_counts = Counter(efficiency.loc[eligible].astype(str).tolist())
            combined_counts = Counter(
                f"{left}|{right}"
                for left, right in zip(
                    risk.loc[eligible].astype(str),
                    efficiency.loc[eligible].astype(str),
                    strict=True,
                )
            )
            candidate: dict[str, object] = {
                "eligible_instrument_count": int(eligible.sum()),
                "risk_state_counts": dict(sorted(risk_counts.items())),
                "efficiency_state_counts": dict(sorted(efficiency_counts.items())),
                "combined_state_counts": dict(sorted(combined_counts.items())),
            }
            if window != TICKER_RISK_REFERENCE_WINDOW:
                candidate["risk_agreement_vs_252"] = ordinal_agreement(
                    risk,
                    reference_risk,
                    RISK_STATE_ORDER,
                )
                candidate["efficiency_agreement_vs_252"] = ordinal_agreement(
                    efficiency,
                    reference_efficiency,
                    EFFICIENCY_STATE_ORDER,
                )
                both = pd.DataFrame(
                    {
                        "risk_short": risk,
                        "risk_ref": reference_risk,
                        "eff_short": efficiency,
                        "eff_ref": reference_efficiency,
                    }
                ).dropna()
                candidate["combined_exact_agreement_vs_252"] = (
                    None
                    if both.empty
                    else float(
                        (
                            (both["risk_short"] == both["risk_ref"])
                            & (both["eff_short"] == both["eff_ref"])
                        ).mean()
                    )
                )
            candidates[str(window)] = candidate

        shortest = TICKER_RISK_LOOKBACK_WINDOWS[0]
        shortest_coverage = coverage[str(shortest)]
        report = TickerRiskProbeReport(
            contract_version=TICKER_RISK_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            as_of_date=as_of_date.isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            history_safety_note=(
                "Only Gate-9 identity-safe current-alias history is considered. Exact authoritative current intervals bound reused/multi-alias tickers; unresolved identities are excluded. No ticker-text splice."
            ),
            threshold_note=(
                "All candidate thresholds are ticker-self-relative and prior-only. The current observation is excluded from the 20/60/126/252-session quantile windows."
            ),
            route_population_count=route_population,
            identity_safe_history_instrument_count=int(len(population)),
            identity_blocked_history_instrument_count=int(route_population - len(population)),
            current_metric_instrument_count=int(len(frame)),
            missing_current_metric_instrument_count=int(len(population) - len(frame)),
            lookback_windows=TICKER_RISK_LOOKBACK_WINDOWS,
            coverage_by_window=coverage,
            insufficient_for_shortest_window_count=int(len(frame) - shortest_coverage),
            candidate_windows=candidates,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
