from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from packages.analogues.policy import (
    PHASE12_BOOTSTRAP_DRAWS,
    PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION,
    PHASE12_PATH_HORIZON_SESSIONS,
    PHASE12_SCENARIO_POLICY_CONTRACT_VERSION,
)
from packages.schemas.deep_research import EmpiricalPathScenarios, ScenarioQuantiles


class EmpiricalScenarioError(ValueError):
    pass


def deterministic_seed(*, instrument_id: str, as_of_date: str, direction: str) -> int:
    payload = "|".join(
        (
            PHASE12_SCENARIO_POLICY_CONTRACT_VERSION,
            instrument_id,
            as_of_date,
            direction,
        )
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _quantiles(values: np.ndarray) -> ScenarioQuantiles:
    q = np.quantile(values, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return ScenarioQuantiles(
        p05=float(q[0]),
        p10=float(q[1]),
        p25=float(q[2]),
        median=float(q[3]),
        p75=float(q[4]),
        p90=float(q[5]),
        p95=float(q[6]),
        mean=float(np.mean(values)),
    )


def build_empirical_path_scenarios(
    path_frame: pd.DataFrame,
    *,
    instrument_id: str,
    as_of_date: str,
    direction: str,
    draws: int = PHASE12_BOOTSTRAP_DRAWS,
) -> EmpiricalPathScenarios:
    if PHASE12_PATH_HORIZON_SESSIONS != 3:
        raise RuntimeError("Phase 12 scenario implementation expects a three-session path horizon")
    if draws < 1:
        raise EmpiricalScenarioError("draw count must be positive")
    seed = deterministic_seed(
        instrument_id=instrument_id,
        as_of_date=as_of_date,
        direction=direction,
    )
    required = {"direction_return_1", "direction_return_2", "direction_return_3"}
    missing = sorted(required.difference(path_frame.columns))
    if missing:
        raise EmpiricalScenarioError("path frame missing columns: " + ", ".join(missing))
    if len(path_frame) < PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION:
        return EmpiricalPathScenarios(
            available=False,
            draw_count=0,
            seed=seed,
            source_path_rows=int(len(path_frame)),
            reason_codes=("PATH_ROWS_BELOW_PREREGISTERED_MINIMUM",),
        )

    matrix = path_frame[
        ["direction_return_1", "direction_return_2", "direction_return_3"]
    ].to_numpy(dtype="float64")
    if not np.isfinite(matrix).all():
        raise EmpiricalScenarioError("path evidence must be finite")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(matrix), size=draws, endpoint=False)
    sampled = matrix[indices]
    max_adverse = np.minimum(0.0, np.min(sampled, axis=1))
    max_favorable = np.maximum(0.0, np.max(sampled, axis=1))
    terminal = sampled[:, 2]
    return EmpiricalPathScenarios(
        available=True,
        draw_count=int(draws),
        seed=seed,
        source_path_rows=int(len(path_frame)),
        session_1=_quantiles(sampled[:, 0]),
        session_2=_quantiles(sampled[:, 1]),
        session_3=_quantiles(terminal),
        max_adverse_excursion=_quantiles(max_adverse),
        max_favorable_excursion=_quantiles(max_favorable),
        terminal_positive_rate=float(np.mean(terminal > 0.0)),
        reason_codes=("DETERMINISTIC_EMPIRICAL_PATH_BOOTSTRAP_AVAILABLE",),
    )
