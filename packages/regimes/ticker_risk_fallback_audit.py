from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .ticker_risk_probe import (
    RISK_STATE_ORDER,
    TICKER_RISK_LOOKBACK_WINDOWS,
    TICKER_RISK_REFERENCE_WINDOW,
    TickerRiskProbe,
)


TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION = (
    "ticker-risk-fallback-audit-v1-current-severity-and-history-cohorts"
)


@dataclass(frozen=True, slots=True)
class TickerRiskFallbackAuditReport:
    contract_version: str
    generated_at_utc: str
    as_of_date: str
    wall_seconds: float
    audit_status: str
    route_population_count: int
    identity_safe_history_instrument_count: int
    identity_blocked_history_instrument_count: int
    exact_current_metric_count: int
    missing_exact_current_metric_count: int
    history_cohort_counts: dict[str, int]
    risk_direction_vs_252: dict[str, dict[str, float | int | None]]
    risk_direction_vs_126: dict[str, dict[str, float | int | None]]
    report_path: str


def directional_ordinal_diagnostics(
    shorter: pd.Series,
    reference: pd.Series,
    order: tuple[str, ...] = RISK_STATE_ORDER,
) -> dict[str, float | int | None]:
    pairs = pd.DataFrame({"shorter": shorter, "reference": reference}).dropna()
    if pairs.empty:
        return {
            "comparison_count": 0,
            "exact_count": 0,
            "exact_rate": None,
            "under_one_count": 0,
            "under_one_rate": None,
            "under_two_plus_count": 0,
            "under_two_plus_rate": None,
            "over_one_count": 0,
            "over_one_rate": None,
            "over_two_plus_count": 0,
            "over_two_plus_rate": None,
            "stressed_as_calm_or_normal_count": 0,
            "stressed_as_calm_or_normal_rate": None,
        }

    ranking = {state: index for index, state in enumerate(order)}
    short_rank = pairs["shorter"].astype(str).map(ranking)
    ref_rank = pairs["reference"].astype(str).map(ranking)
    delta = short_rank - ref_rank
    count = int(len(pairs))
    exact = int((delta == 0).sum())
    under_one = int((delta == -1).sum())
    under_two_plus = int((delta <= -2).sum())
    over_one = int((delta == 1).sum())
    over_two_plus = int((delta >= 2).sum())
    stressed_mask = pairs["reference"].astype(str) == "STRESSED"
    stressed_count = int(stressed_mask.sum())
    stressed_bad = int(
        (
            stressed_mask
            & pairs["shorter"].astype(str).isin({"CALM", "NORMAL"})
        ).sum()
    )
    return {
        "comparison_count": count,
        "exact_count": exact,
        "exact_rate": exact / count,
        "under_one_count": under_one,
        "under_one_rate": under_one / count,
        "under_two_plus_count": under_two_plus,
        "under_two_plus_rate": under_two_plus / count,
        "over_one_count": over_one,
        "over_one_rate": over_one / count,
        "over_two_plus_count": over_two_plus,
        "over_two_plus_rate": over_two_plus / count,
        "stressed_reference_count": stressed_count,
        "stressed_as_calm_or_normal_count": stressed_bad,
        "stressed_as_calm_or_normal_rate": (
            None if stressed_count == 0 else stressed_bad / stressed_count
        ),
    }


def history_cohort_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty:
        return {
            "<20": 0,
            "20-59": 0,
            "60-125": 0,
            "126-251": 0,
            ">=252": 0,
        }
    depth = pd.to_numeric(frame["prior_count_252"], errors="coerce").fillna(0)
    return {
        "<20": int((depth < 20).sum()),
        "20-59": int(((depth >= 20) & (depth < 60)).sum()),
        "60-125": int(((depth >= 60) & (depth < 126)).sum()),
        "126-251": int(((depth >= 126) & (depth < 252)).sum()),
        ">=252": int((depth >= 252).sum()),
    }


class TickerRiskFallbackAudit:
    """Audit shorter self-relative risk windows for optimistic severity errors."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.probe = TickerRiskProbe(settings)

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return (
            root
            / "regimes"
            / "ticker_risk_fallback_audit"
            / f"{as_of_date.year:04d}"
            / f"{as_of_date}.json"
        )

    def run(self, as_of_date: date) -> TickerRiskFallbackAuditReport:
        started = perf_counter()
        population, route_population = self.probe._identity_safe_population(as_of_date)
        frame = self.probe._current_quantile_frame(population, as_of_date)
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        risk_states: dict[int, pd.Series] = {}
        for window in TICKER_RISK_LOOKBACK_WINDOWS:
            risk, _ = self.probe._classify_window(frame, window)
            risk_states[window] = risk

        reference_252 = risk_states[TICKER_RISK_REFERENCE_WINDOW]
        reference_126 = risk_states[126]
        versus_252 = {
            str(window): directional_ordinal_diagnostics(risk_states[window], reference_252)
            for window in (20, 60, 126)
        }
        versus_126 = {
            str(window): directional_ordinal_diagnostics(risk_states[window], reference_126)
            for window in (20, 60)
        }

        report = TickerRiskFallbackAuditReport(
            contract_version=TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            as_of_date=as_of_date.isoformat(),
            wall_seconds=perf_counter() - started,
            audit_status="EVIDENCE_ONLY",
            route_population_count=route_population,
            identity_safe_history_instrument_count=int(len(population)),
            identity_blocked_history_instrument_count=int(route_population - len(population)),
            exact_current_metric_count=int(len(frame)),
            missing_exact_current_metric_count=int(len(population) - len(frame)),
            history_cohort_counts=history_cohort_counts(frame),
            risk_direction_vs_252=versus_252,
            risk_direction_vs_126=versus_126,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
