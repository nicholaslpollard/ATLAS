from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.ml.outcome_family_audit import MLOutcomeFamilyAudit
from packages.ml.universe_probe import ML_HISTORY_ORIGIN_DATE


ML_LABEL_POLICY_PROBE_CONTRACT_VERSION = (
    "ml-label-policy-probe-v1-annual-stability-3-5-10-natr-grid"
)
ML_LABEL_POLICY_CANDIDATE_HORIZONS = (3, 5, 10)
ML_LABEL_POLICY_CANDIDATE_MULTIPLIERS = (0.5, 1.0)
ML_LABEL_POLICY_PRIMARY_CANDIDATE_MULTIPLIER = 0.5


@dataclass(frozen=True, slots=True)
class AnnualLabelEvidence:
    year: int
    usable_rows: int
    up_rows: int
    down_rows: int
    neutral_rows: int
    directional_rows: int
    up_fraction: float
    down_fraction: float
    neutral_fraction: float
    directional_fraction: float
    up_fraction_of_directional: float


@dataclass(frozen=True, slots=True)
class CandidateLabelEvidence:
    horizon_sessions: int
    multiplier: float
    usable_rows: int
    up_rows: int
    down_rows: int
    neutral_rows: int
    directional_fraction: float
    up_fraction_of_directional: float
    annual_directional_fraction_range: float
    annual_up_fraction_of_directional_range: float
    annual_evidence: tuple[AnnualLabelEvidence, ...]


@dataclass(frozen=True, slots=True)
class MLLabelPolicyProbeReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    candidate_horizons: tuple[int, ...]
    candidate_multipliers: tuple[float, ...]
    primary_candidate_multiplier: float
    split_crossing_windows_censored: bool
    exact_session_continuity_required: bool
    same_provider_ticker_required: bool
    endpoint_outcome_only: bool
    candidates: tuple[CandidateLabelEvidence, ...]
    prediction_label_policy_locked: bool
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def stability_range(values: list[float]) -> float:
    return 0.0 if not values else float(max(values) - min(values))


class MLLabelPolicyProbe:
    """Compare plausible Gate 4 label candidates across annual cohorts.

    Gate 3 established that split-censored, exact-session endpoint labels are feasible
    and that 0.5x NATR provides materially better class support than the sparser tail
    thresholds. Gate 4 now compares 3/5/10-session horizons, with 1.0x retained only
    as a sensitivity reference, before a production target is locked.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.family = MLOutcomeFamilyAudit(settings)
        self.base = self.family.base

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "label_policy_probe" / f"{end_date.year:04d}" / f"{end_date}.json"

    def _candidate_evidence(
        self,
        con: Any,
        *,
        horizon: int,
        multiplier: float,
    ) -> CandidateLabelEvidence:
        threshold = f"natr_14 * sqrt({float(horizon)}) * {float(multiplier)}"
        ret = "(future_close / close) - 1.0"
        rows = con.execute(
            f"""
            WITH outcome AS (
                SELECT
                    c.symbol,
                    c.session_date,
                    c.close,
                    c.natr_14,
                    fs.session_date AS future_date,
                    fb.close AS future_close,
                    EXISTS (
                        SELECT 1
                        FROM ml_split_events s
                        WHERE s.ticker = c.symbol
                          AND s.execution_date > c.session_date
                          AND s.execution_date <= fs.session_date
                    ) AS split_crossing
                FROM ml_gate3_scaled_candidates c
                LEFT JOIN ml_label_sessions fs
                  ON fs.session_seq = c.session_seq + {int(horizon)}
                LEFT JOIN ml_label_bars fb
                  ON fb.symbol = c.symbol
                 AND fb.session_date = fs.session_date
            ), usable AS (
                SELECT *
                FROM outcome
                WHERE future_date IS NOT NULL
                  AND future_close > 0
                  AND NOT split_crossing
            )
            SELECT
                year(session_date) AS cohort_year,
                count(*) AS usable_rows,
                count(*) FILTER (WHERE {ret} >= {threshold}) AS up_rows,
                count(*) FILTER (WHERE {ret} <= -({threshold})) AS down_rows,
                count(*) FILTER (
                    WHERE {ret} < {threshold} AND {ret} > -({threshold})
                ) AS neutral_rows
            FROM usable
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()

        annual: list[AnnualLabelEvidence] = []
        for raw in rows:
            year_value = int(raw[0])
            usable_rows = int(raw[1])
            up_rows = int(raw[2])
            down_rows = int(raw[3])
            neutral_rows = int(raw[4])
            directional_rows = up_rows + down_rows
            annual.append(
                AnnualLabelEvidence(
                    year=year_value,
                    usable_rows=usable_rows,
                    up_rows=up_rows,
                    down_rows=down_rows,
                    neutral_rows=neutral_rows,
                    directional_rows=directional_rows,
                    up_fraction=_fraction(up_rows, usable_rows),
                    down_fraction=_fraction(down_rows, usable_rows),
                    neutral_fraction=_fraction(neutral_rows, usable_rows),
                    directional_fraction=_fraction(directional_rows, usable_rows),
                    up_fraction_of_directional=_fraction(up_rows, directional_rows),
                )
            )

        usable_rows = sum(item.usable_rows for item in annual)
        up_rows = sum(item.up_rows for item in annual)
        down_rows = sum(item.down_rows for item in annual)
        neutral_rows = sum(item.neutral_rows for item in annual)
        directional_rows = up_rows + down_rows
        return CandidateLabelEvidence(
            horizon_sessions=horizon,
            multiplier=multiplier,
            usable_rows=usable_rows,
            up_rows=up_rows,
            down_rows=down_rows,
            neutral_rows=neutral_rows,
            directional_fraction=_fraction(directional_rows, usable_rows),
            up_fraction_of_directional=_fraction(up_rows, directional_rows),
            annual_directional_fraction_range=stability_range(
                [item.directional_fraction for item in annual]
            ),
            annual_up_fraction_of_directional_range=stability_range(
                [item.up_fraction_of_directional for item in annual if item.directional_rows > 0]
            ),
            annual_evidence=tuple(annual),
        )

    def run(self, end_date: date) -> MLLabelPolicyProbeReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")

        splits, _ = self.family._load_split_evidence(end_date)
        con = connect_utc(":memory:")
        try:
            self.base._prepare_label_views(con, end_date, splits)
            self.family._prepare_scaled_candidates(con)
            candidates = tuple(
                self._candidate_evidence(
                    con,
                    horizon=horizon,
                    multiplier=multiplier,
                )
                for horizon in ML_LABEL_POLICY_CANDIDATE_HORIZONS
                for multiplier in ML_LABEL_POLICY_CANDIDATE_MULTIPLIERS
            )
        finally:
            con.close()

        target = self.report_path(end_date)
        report = MLLabelPolicyProbeReport(
            contract_version=ML_LABEL_POLICY_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            candidate_horizons=ML_LABEL_POLICY_CANDIDATE_HORIZONS,
            candidate_multipliers=ML_LABEL_POLICY_CANDIDATE_MULTIPLIERS,
            primary_candidate_multiplier=ML_LABEL_POLICY_PRIMARY_CANDIDATE_MULTIPLIER,
            split_crossing_windows_censored=True,
            exact_session_continuity_required=True,
            same_provider_ticker_required=True,
            endpoint_outcome_only=True,
            candidates=candidates,
            prediction_label_policy_locked=False,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
