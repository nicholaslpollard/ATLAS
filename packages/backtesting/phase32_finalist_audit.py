from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase32_policy import (
    PHASE32_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE32_BOOTSTRAP_REPLICATES,
    PHASE32_BOOTSTRAP_SEED,
    PHASE32_CANDIDATES,
    PHASE32_COST_GRID_BPS,
    PHASE32_DEVELOPMENT_LAST_SIGNAL,
    PHASE32_INTERNAL_CONFIDENCE,
    PHASE32_INTERNAL_MIN_EVENT_ROWS,
    PHASE32_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_INTERNAL_PURGE_SESSIONS,
    PHASE32_INTERNAL_VALIDATION_FOLDS,
    PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION,
    PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE32_MIN_POSITIVE_REGIME_FRACTION,
    PHASE32_MIN_POSITIVE_YEAR_FRACTION,
    PHASE32_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE32_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE32_MULTIPLE_TESTING_ALPHA,
    PHASE32_MULTIPLE_TESTING_METHOD,
    PHASE32_PRIMARY_COST_BPS,
    PHASE32_PROTECTED_FOLDS,
    PHASE32_PROTECTED_LAST_SIGNAL,
    PHASE32_PROTECTED_MIN_EVENT_ROWS,
    PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
    PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_PROTECTED_OUTCOME_END,
    PHASE32_PROTECTED_START,
    PHASE32_RESEARCH_SIGNAL_START,
    PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE32_SELECTION_CONFIDENCE,
    PHASE32_SELECTION_FOLDS,
    PHASE32_SELECTION_FRACTION,
    PHASE32_SELECTION_MIN_EVENT_ROWS,
    PHASE32_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_SELECTION_WINNER_RULE,
    PHASE32_STRESS_COST_BPS,
    phase32_policy_fingerprint,
)
from .phase32_predictor_acceptance import (
    PHASE32_ACCEPTANCE_RELATIVE,
    PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
)
from .phase32_predictor_acquisition import (
    PHASE32_EVIDENCE_RELATIVE,
    PHASE32_FROZEN_POLICY_FINGERPRINT,
    PHASE32_PREDICTORS_RELATIVE,
)

PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION = (
    "phase32-finalist-blindness-lineage-audit-v1-independent-development-recompute-protected-unread"
)
PHASE32_PROTECTED_PLAN_CONTRACT_VERSION = (
    "phase32-protected-plan-v1-finalist-only-source-predictor-three-fold-no-returns"
)
PHASE32_EXPECTED_DEVELOPMENT_CONTRACT_VERSION = (
    "phase32-development-study-v1-open-t5-spy-relative-five-hypothesis-protected-blind"
)
PHASE32_EXPECTED_FINALIST_ARTIFACT_CONTRACT_VERSION = (
    "phase32-finalists-v1-selection-internal-protected-returns-unread"
)
PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT = (
    "531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde"
)
PHASE32_EXPECTED_DEVELOPMENT_TARGET_ROWS = 18_819
PHASE32_EXPECTED_DEVELOPMENT_USABLE_ROWS = 18_448
PHASE32_EXPECTED_MISSING_EXACT_STOCK_PATH_ROWS = 294
PHASE32_EXPECTED_SPLIT_CROSSING_ROWS = 79
PHASE32_EXPECTED_SELECTION_SURVIVORS = (
    "equity_issuance_short",
    "financial_integrity_adverse_short",
    "listing_distress_short",
    "share_repurchase_long",
    "solvency_distress_short",
)
PHASE32_EXPECTED_SELECTION_WINNERS = (
    "share_repurchase_long",
    "solvency_distress_short",
)
PHASE32_EXPECTED_FINALISTS = ("solvency_distress_short",)

_DEVELOPMENT_RELATIVE = Path("strategy_evaluation") / "phase32" / "v1" / "development"
_FORBIDDEN_PREDICTOR_OUTCOME_FIELDS = {
    "entry_open",
    "exit_close",
    "spy_entry_open",
    "spy_exit_close",
    "stock_return",
    "spy_return",
    "primary_gross_return",
    "unhedged_gross_return",
}
_PLAN_FORBIDDEN_FIELDS = _FORBIDDEN_PREDICTOR_OUTCOME_FIELDS | {
    "primary_mean_return",
    "primary_lcb",
    "stress_mean_return",
    "protected_return",
}


class Phase32FinalistAuditError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase32FinalistAuditError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase32FinalistAuditError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase32FinalistAuditError(f"{label} must be a JSON object")
    return payload


def _read_jsonl(path: Path, *, label: str) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        raise Phase32FinalistAuditError(f"missing {label}: {path}")
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Phase32FinalistAuditError(f"cannot read {label}: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Phase32FinalistAuditError(f"invalid {label} row: {path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise Phase32FinalistAuditError(f"{label} row is not an object: {path}:{line_number}")
        rows.append(row)
    return tuple(rows)


def _read_parquet(path: Path, *, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase32FinalistAuditError(f"missing {label}: {path}")
    con = connect_utc(":memory:")
    try:
        return con.execute(f"SELECT * FROM read_parquet({sql_string(path)})").fetch_df()
    except Exception as exc:  # DuckDB surface varies by platform/version.
        raise Phase32FinalistAuditError(f"cannot read {label}: {path}") from exc
    finally:
        con.close()


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    materialized = tuple(dict(row) for row in rows)
    text = "".join(_canonical_json(row) + "\n" for row in materialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)


def _derived_seed(label: str) -> int:
    return PHASE32_BOOTSTRAP_SEED + int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def independent_block_bootstrap(
    values: np.ndarray,
    *,
    confidence: float,
    label: str,
) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase32FinalistAuditError("independent bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE32_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE32_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(PHASE32_BOOTSTRAP_REPLICATES, -1)[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    null_means = (values - observed)[indices].mean(axis=1)
    p_value = float((1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1))
    return lower, p_value


def independent_holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = PHASE32_MULTIPLE_TESTING_ALPHA,
) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), str(key)) for key, value in p_values.items())
    result: dict[str, dict[str, object]] = {}
    active = True
    total = len(ordered)
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(active and p_value <= threshold)
        result[key] = {
            "p_value": p_value,
            "threshold": threshold,
            "rejected_null": reject,
        }
        if not reject:
            active = False
    return result


def _fraction_positive(values: Mapping[str, float]) -> float | None:
    if not values:
        return None
    return float(sum(value > 0 for value in values.values()) / len(values))


def _fold_mapping(sessions: tuple[date, ...], folds: int) -> dict[date, int]:
    if folds <= 0 or len(sessions) < folds:
        raise Phase32FinalistAuditError("invalid frozen fold grid")
    blocks = [tuple(block.tolist()) for block in np.array_split(np.asarray(sessions, dtype=object), folds)]
    return {session: index for index, block in enumerate(blocks) for session in block}


def _assign_fold(frame: pd.DataFrame, *, mapping: Mapping[date, int], field: str) -> pd.DataFrame:
    result = frame.copy()
    result["decision_session"] = pd.to_datetime(result["decision_session"]).dt.date
    result[field] = result["decision_session"].map(mapping)
    if not result.empty and result[field].isna().any():
        raise Phase32FinalistAuditError(f"independent audit found incomplete {field} attribution")
    if not result.empty:
        result[field] = result[field].astype(int)
    return result


def _boundaries(calendar: Any) -> dict[str, object]:
    start = date.fromisoformat(PHASE32_RESEARCH_SIGNAL_START)
    end = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
    sessions = tuple(calendar.sessions_in_range(start, end))
    if not sessions or sessions[0] != start or sessions[-1] != end:
        raise Phase32FinalistAuditError("independent development calendar does not match frozen scope")
    selection_count = int(math.floor(len(sessions) * PHASE32_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE32_INTERNAL_PURGE_SESSIONS
    selection = sessions[:selection_count]
    purge = sessions[selection_count:internal_offset]
    internal = sessions[internal_offset:]
    if not selection or len(purge) != PHASE32_INTERNAL_PURGE_SESSIONS or not internal:
        raise Phase32FinalistAuditError("independent development split is incomplete")
    return {
        "sessions": sessions,
        "selection": selection,
        "purge": purge,
        "internal": internal,
        "selection_start": selection[0],
        "selection_end": selection[-1],
        "internal_start": internal[0],
        "internal_end": internal[-1],
    }


def _eligible_state_means(data: pd.DataFrame, *, state_field: str, primary_cost: float) -> dict[str, float]:
    subset = data.loc[
        data[state_field].notna(),
        ["decision_session", state_field, "primary_gross_return"],
    ].copy()
    if subset.empty:
        return {}
    subset[state_field] = subset[state_field].astype(str)
    grouped = (
        subset.groupby([state_field, "decision_session"], sort=True, observed=True)["primary_gross_return"]
        .mean()
        .reset_index()
    )
    result: dict[str, float] = {}
    for state, state_rows in grouped.groupby(state_field, sort=True, observed=True):
        if state_rows["decision_session"].nunique() >= PHASE32_MIN_REGIME_SIGNAL_SESSIONS:
            result[str(state)] = float(
                pd.to_numeric(state_rows["primary_gross_return"], errors="coerce").mean() - primary_cost
            )
    return result


def _fold_means(
    session: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    fold_field: str,
    fold_count: int,
    primary_cost: float,
) -> list[float | None]:
    if signals.empty:
        return [None for _ in range(fold_count)]
    mapping = signals[["decision_session", fold_field]].drop_duplicates()
    if mapping.duplicated(["decision_session"], keep=False).any():
        raise Phase32FinalistAuditError("independent audit found a session in multiple folds")
    merged = session.merge(mapping, on="decision_session", how="left", validate="one_to_one")
    if merged[fold_field].isna().any():
        raise Phase32FinalistAuditError("independent audit found missing fold attribution")
    values: list[float | None] = []
    for fold in range(fold_count):
        group = merged.loc[merged[fold_field] == fold]
        values.append(None if group.empty else float(group["primary_gross_return"].mean() - primary_cost))
    return values


def independent_metrics(
    signals: pd.DataFrame,
    *,
    confidence: float,
    fold_field: str,
    fold_count: int,
    label: str,
) -> dict[str, object]:
    if signals.empty:
        return {
            "raw_rows": 0,
            "signal_sessions": 0,
            "unique_instruments": 0,
            "cost_mean_returns": {},
            "primary_mean_return": None,
            "unhedged_primary_mean_return": None,
            "primary_median_event_return": None,
            "primary_event_win_rate": None,
            "primary_session_win_rate": None,
            "primary_lcb": None,
            "primary_bootstrap_p_value": None,
            "stress_mean_return": None,
            "max_single_session_row_fraction": None,
            "max_single_instrument_row_fraction": None,
            "fold_means": [None for _ in range(fold_count)],
            "positive_folds": 0,
            "eligible_year_means": {},
            "positive_year_fraction": None,
            "eligible_market_state_means": {},
            "positive_market_state_fraction": None,
            "eligible_ticker_state_means": {},
            "positive_ticker_state_fraction": None,
            "session_sharpe": None,
        }
    data = signals.copy()
    data["decision_session"] = pd.to_datetime(data["decision_session"]).dt.date
    for field in ("primary_gross_return", "unhedged_gross_return"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    finite = (
        np.isfinite(data["primary_gross_return"].to_numpy(dtype=float))
        & np.isfinite(data["unhedged_gross_return"].to_numpy(dtype=float))
    )
    data = data.loc[finite].copy()
    if data.empty:
        return independent_metrics(
            data,
            confidence=confidence,
            fold_field=fold_field,
            fold_count=fold_count,
            label=label,
        )
    primary_cost = PHASE32_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE32_STRESS_COST_BPS / 10_000.0
    session = (
        data.groupby("decision_session", sort=True, observed=True)
        .agg(
            primary_gross_return=("primary_gross_return", "mean"),
            unhedged_gross_return=("unhedged_gross_return", "mean"),
            row_count=("instrument_id", "size"),
        )
        .reset_index()
        .sort_values("decision_session", kind="stable")
    )
    gross = session["primary_gross_return"].to_numpy(dtype=float)
    primary = gross - primary_cost
    unhedged = session["unhedged_gross_return"].to_numpy(dtype=float) - primary_cost
    stress = gross - stress_cost
    lower, p_value = independent_block_bootstrap(primary, confidence=confidence, label=label)
    fold_values = _fold_means(
        session,
        data,
        fold_field=fold_field,
        fold_count=fold_count,
        primary_cost=primary_cost,
    )
    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["decision_session"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {
        str(year): float(np.mean(values))
        for year, values in sorted(year_values.items())
        if len(values) >= PHASE32_MIN_YEAR_SIGNAL_SESSIONS
    }
    market_means = _eligible_state_means(
        data,
        state_field="prior_market_state",
        primary_cost=primary_cost,
    )
    ticker_means = _eligible_state_means(
        data,
        state_field="prior_ticker_state",
        primary_cost=primary_cost,
    )
    cost_means = {
        f"{float(cost):g}": float(np.mean(gross - float(cost) / 10_000.0))
        for cost in PHASE32_COST_GRID_BPS
    }
    event_primary = data["primary_gross_return"].to_numpy(dtype=float) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = None if primary_std <= 0 else float(np.mean(primary) / primary_std)
    raw_rows = int(len(data))
    instrument_counts = data.groupby("instrument_id", sort=True, observed=True).size()
    max_instrument_fraction = (
        None if instrument_counts.empty else float(instrument_counts.max() / raw_rows)
    )
    return {
        "raw_rows": raw_rows,
        "signal_sessions": int(len(session)),
        "unique_instruments": int(data["instrument_id"].nunique()),
        "cost_mean_returns": cost_means,
        "primary_mean_return": float(np.mean(primary)),
        "unhedged_primary_mean_return": float(np.mean(unhedged)),
        "primary_median_event_return": float(np.median(event_primary)),
        "primary_event_win_rate": float(np.mean(event_primary > 0)),
        "primary_session_win_rate": float(np.mean(primary > 0)),
        "primary_lcb": lower,
        "primary_bootstrap_p_value": p_value,
        "stress_mean_return": float(np.mean(stress)),
        "max_single_session_row_fraction": float(session["row_count"].max() / raw_rows),
        "max_single_instrument_row_fraction": max_instrument_fraction,
        "fold_means": fold_values,
        "positive_folds": sum(value is not None and value > 0 for value in fold_values),
        "eligible_year_means": year_means,
        "positive_year_fraction": _fraction_positive(year_means),
        "eligible_market_state_means": market_means,
        "positive_market_state_fraction": _fraction_positive(market_means),
        "eligible_ticker_state_means": ticker_means,
        "positive_ticker_state_fraction": _fraction_positive(ticker_means),
        "session_sharpe": session_sharpe,
    }


def _stage_checks(
    metrics: Mapping[str, object],
    *,
    min_event_rows: int,
    min_signal_sessions: int,
    min_unique_instruments: int,
    min_positive_folds: int,
) -> dict[str, bool]:
    def number(name: str) -> float | None:
        value = metrics.get(name)
        return None if value is None else float(value)

    return {
        "min_event_rows": int(metrics["raw_rows"]) >= min_event_rows,
        "min_signal_sessions": int(metrics["signal_sessions"]) >= min_signal_sessions,
        "min_unique_instruments": int(metrics["unique_instruments"]) >= min_unique_instruments,
        "positive_folds": int(metrics["positive_folds"]) >= min_positive_folds,
        "primary_mean_positive": bool(number("primary_mean_return") is not None and number("primary_mean_return") > 0),
        "primary_lcb_positive": bool(number("primary_lcb") is not None and number("primary_lcb") > 0),
        "stress_mean_positive": bool(number("stress_mean_return") is not None and number("stress_mean_return") > 0),
        "unhedged_primary_mean_positive": bool(
            number("unhedged_primary_mean_return") is not None
            and number("unhedged_primary_mean_return") > 0
        ),
        "year_robustness": bool(
            number("positive_year_fraction") is not None
            and number("positive_year_fraction") >= PHASE32_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": bool(
            number("positive_market_state_fraction") is not None
            and number("positive_market_state_fraction") >= PHASE32_MIN_POSITIVE_REGIME_FRACTION
        ),
        "ticker_state_robustness": bool(
            number("positive_ticker_state_fraction") is not None
            and number("positive_ticker_state_fraction") >= PHASE32_MIN_POSITIVE_REGIME_FRACTION
        ),
        "session_concentration": bool(
            number("max_single_session_row_fraction") is not None
            and number("max_single_session_row_fraction") <= PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
        "instrument_concentration": bool(
            number("max_single_instrument_row_fraction") is not None
            and number("max_single_instrument_row_fraction") <= PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION
        ),
    }


def _assert_equivalent(actual: object, expected: object, *, label: str) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        if set(actual) != set(expected):
            raise Phase32FinalistAuditError(f"{label} key set differs")
        for key in sorted(actual):
            _assert_equivalent(actual[key], expected[key], label=f"{label}.{key}")
        return
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            raise Phase32FinalistAuditError(f"{label} length differs")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            _assert_equivalent(left, right, label=f"{label}[{index}]")
        return
    if isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        if actual is None or expected is None:
            if actual is not expected:
                raise Phase32FinalistAuditError(f"{label} differs: {actual!r} != {expected!r}")
            return
        if not math.isclose(float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-12):
            raise Phase32FinalistAuditError(f"{label} differs: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise Phase32FinalistAuditError(f"{label} differs: {actual!r} != {expected!r}")


def protected_source_sample_gate(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    materialized = tuple(rows)
    sessions = {str(row.get("decision_session") or "") for row in materialized}
    instruments = {str(row.get("instrument_id") or "") for row in materialized}
    sessions.discard("")
    instruments.discard("")
    checks = {
        "min_event_rows": len(materialized) >= PHASE32_PROTECTED_MIN_EVENT_ROWS,
        "min_signal_sessions": len(sessions) >= PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
        "min_unique_instruments": len(instruments) >= PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    }
    return {
        "event_rows": len(materialized),
        "signal_sessions": len(sessions),
        "unique_instruments": len(instruments),
        "checks": checks,
        "possible": all(checks.values()),
    }


def resolve_protected_execution_tickers(
    predictor_rows: Iterable[Mapping[str, object]],
    filing_entity_rows: Iterable[Mapping[str, object]],
    *,
    finalist_ids: Iterable[str],
) -> dict[tuple[str, str, str], str]:
    finalist_set = set(finalist_ids)
    predictor_keys = {
        (
            str(row.get("instrument_id") or "").strip(),
            str(row.get("decision_session") or "").strip(),
            str(row.get("candidate_id") or "").strip(),
        )
        for row in predictor_rows
        if str(row.get("stage") or "") == "protected_predictor_only"
        and str(row.get("candidate_id") or "") in finalist_set
    }
    if any(not all(key) for key in predictor_keys):
        raise Phase32FinalistAuditError("protected finalist predictor key is incomplete")
    ticker_sets: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in filing_entity_rows:
        if row.get("eligibility") != "eligible" or str(row.get("stage") or "") != "protected_predictor_only":
            continue
        instrument = row.get("instrument")
        if not isinstance(instrument, Mapping):
            raise Phase32FinalistAuditError("eligible protected filing entity lacks instrument evidence")
        instrument_id = str(instrument.get("instrument_id") or "").strip()
        ticker = str(instrument.get("ticker") or "").strip()
        decision_session = str(row.get("decision_session") or "").strip()
        if not instrument_id or not ticker or not decision_session:
            raise Phase32FinalistAuditError("eligible protected filing entity has incomplete execution identity")
        for candidate_id in row.get("candidate_ids") or []:
            key = (instrument_id, decision_session, str(candidate_id))
            if key in predictor_keys:
                ticker_sets[key].add(ticker)
    missing = sorted(predictor_keys - set(ticker_sets))
    if missing:
        raise Phase32FinalistAuditError(
            "protected finalist predictor lacks execution-ticker lineage: " + repr(missing[:3])
        )
    ambiguous = sorted(
        (key, sorted(values))
        for key, values in ticker_sets.items()
        if key in predictor_keys and len(values) != 1
    )
    if ambiguous:
        raise Phase32FinalistAuditError(
            "protected finalist execution ticker is ambiguous before outcomes: " + repr(ambiguous[:3])
        )
    return {key: next(iter(ticker_sets[key])) for key in sorted(predictor_keys)}


class Phase32FinalistBlindnessAudit:
    """Independent development-result audit and protected finalist source-only plan freeze."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.development_root = self.derived_root / _DEVELOPMENT_RELATIVE
        self.predictor_path = self.derived_root / PHASE32_PREDICTORS_RELATIVE
        self.acceptance_path = self.derived_root / PHASE32_ACCEPTANCE_RELATIVE
        self.filing_entity_path = (
            self.provider_root / PHASE32_EVIDENCE_RELATIVE / "candidate_filing_entity_records.jsonl"
        )
        self.audit_root = self.derived_root / "strategy_evaluation" / "phase32" / "v1" / "finalist_audit"

    def report_path(self) -> Path:
        return self.audit_root / "finalist_blindness_audit.json"

    def protected_plan_path(self) -> Path:
        return self.audit_root / "protected_plan.json"

    def protected_plan_rows_path(self) -> Path:
        return self.audit_root / "protected_plan_rows.jsonl"

    def _verify_development_artifacts(self) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
        report_path = self.development_root / "development_study.json"
        finalists_path = self.development_root / "finalists.json"
        outcomes_path = self.development_root / "development_outcomes.parquet"
        signals_path = self.development_root / "development_signals.parquet"
        report = _read_json(report_path, label="Phase32 development study")
        finalists = _read_json(finalists_path, label="Phase32 finalist artifact")
        if report.get("contract_version") != PHASE32_EXPECTED_DEVELOPMENT_CONTRACT_VERSION:
            raise Phase32FinalistAuditError("development study contract drifted")
        if finalists.get("contract_version") != PHASE32_EXPECTED_FINALIST_ARTIFACT_CONTRACT_VERSION:
            raise Phase32FinalistAuditError("finalist artifact contract drifted")
        if report.get("pass") is not True or report.get("status") != "DEVELOPMENT_STUDY_PASS":
            raise Phase32FinalistAuditError("development study is not accepted PASS evidence")
        if report.get("phase32_policy_fingerprint") != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32FinalistAuditError("development policy fingerprint drifted")
        if report.get("source_independent_acceptance_fingerprint") != PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT:
            raise Phase32FinalistAuditError("development independent-acceptance lineage drifted")
        if report.get("source_predictor_sha256") != PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256:
            raise Phase32FinalistAuditError("development predictor lineage drifted")
        if report.get("source_filing_entity_evidence_sha256") != PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256:
            raise Phase32FinalistAuditError("development filing-entity lineage drifted")
        if int(report.get("development_target_rows_read", -1)) != PHASE32_EXPECTED_DEVELOPMENT_TARGET_ROWS:
            raise Phase32FinalistAuditError("development target-row count differs from accepted target-machine result")
        if int(report.get("development_usable_outcome_rows", -1)) != PHASE32_EXPECTED_DEVELOPMENT_USABLE_ROWS:
            raise Phase32FinalistAuditError("development usable-row count differs from accepted target-machine result")
        exclusions = report.get("outcome_path_exclusions")
        if not isinstance(exclusions, Mapping):
            raise Phase32FinalistAuditError("development path exclusions are missing")
        if int(exclusions.get("exact_stock_path_missing_rows", -1)) != PHASE32_EXPECTED_MISSING_EXACT_STOCK_PATH_ROWS:
            raise Phase32FinalistAuditError("accepted missing exact stock-path count drifted")
        if int(exclusions.get("split_crossing_censored_rows", -1)) != PHASE32_EXPECTED_SPLIT_CROSSING_ROWS:
            raise Phase32FinalistAuditError("accepted split-crossing count drifted")
        if int(report.get("protected_return_rows_read", -1)) != 0 or report.get("protected_holdout_consumed") is not False:
            raise Phase32FinalistAuditError("development evidence reports protected holdout consumption")
        for field in (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "automation_writes",
        ):
            if int(report.get(field, -1)) != 0:
                raise Phase32FinalistAuditError(f"development evidence contains forbidden activity: {field}")
        if not outcomes_path.is_file() or sha256_file(outcomes_path) != report.get("development_outcomes_sha256"):
            raise Phase32FinalistAuditError("development outcome artifact hash mismatch")
        if not signals_path.is_file() or sha256_file(signals_path) != report.get("development_signals_sha256"):
            raise Phase32FinalistAuditError("development signal artifact hash mismatch")
        if sha256_file(finalists_path) != report.get("finalists_sha256"):
            raise Phase32FinalistAuditError("development finalist artifact hash mismatch")
        if finalists.get("development_outcomes_sha256") != report.get("development_outcomes_sha256"):
            raise Phase32FinalistAuditError("finalist/outcome lineage mismatch")
        if finalists.get("development_signals_sha256") != report.get("development_signals_sha256"):
            raise Phase32FinalistAuditError("finalist/signal lineage mismatch")
        if finalists.get("frozen") is not True or finalists.get("runner_up_substitution_allowed") is not False:
            raise Phase32FinalistAuditError("finalist artifact is not frozen fail-closed")
        if int(finalists.get("protected_return_rows_read", -1)) != 0 or finalists.get("protected_holdout_consumed") is not False:
            raise Phase32FinalistAuditError("finalist artifact reports protected holdout consumption")
        outcomes = _read_parquet(outcomes_path, label="Phase32 development outcomes")
        if len(outcomes) != PHASE32_EXPECTED_DEVELOPMENT_USABLE_ROWS:
            raise Phase32FinalistAuditError("development outcome parquet row count drifted")
        return report, finalists, outcomes

    def _recompute_development(self, outcomes: pd.DataFrame, report: Mapping[str, Any]) -> dict[str, object]:
        required = {
            "candidate_id",
            "direction",
            "instrument_id",
            "decision_session",
            "prior_state_session",
            "prior_market_state",
            "prior_ticker_state",
            "entry_open",
            "exit_close",
            "spy_entry_open",
            "spy_exit_close",
            "stock_return",
            "spy_return",
            "primary_gross_return",
            "unhedged_gross_return",
        }
        missing = required - set(outcomes.columns)
        if missing:
            raise Phase32FinalistAuditError("development outcomes lack required columns: " + ", ".join(sorted(missing)))
        frame = outcomes.copy()
        frame["decision_session"] = pd.to_datetime(frame["decision_session"]).dt.date
        frame["prior_state_session"] = pd.to_datetime(frame["prior_state_session"]).dt.date
        if bool((frame["prior_state_session"] >= frame["decision_session"]).any()):
            raise Phase32FinalistAuditError("development outcomes contain non-prior regime state")
        if frame["decision_session"].max() > date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL):
            raise Phase32FinalistAuditError("development outcome crossed the protected signal boundary")
        for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
            values = frame[field].to_numpy(dtype=float)
            if not np.isfinite(values).all() or bool((values <= 0).any()):
                raise Phase32FinalistAuditError(f"development outcomes contain invalid {field}")
        stock_return = frame["exit_close"] / frame["entry_open"] - 1.0
        spy_return = frame["spy_exit_close"] / frame["spy_entry_open"] - 1.0
        direction = np.where(frame["direction"].astype(str).eq("LONG"), 1.0, -1.0)
        primary_gross = direction * (stock_return - spy_return)
        unhedged_gross = direction * stock_return
        for field, recomputed in (
            ("stock_return", stock_return),
            ("spy_return", spy_return),
            ("primary_gross_return", primary_gross),
            ("unhedged_gross_return", unhedged_gross),
        ):
            observed = pd.to_numeric(frame[field], errors="coerce").to_numpy(dtype=float)
            if not np.allclose(observed, np.asarray(recomputed, dtype=float), rtol=1e-12, atol=1e-14):
                raise Phase32FinalistAuditError(f"development {field} geometry does not independently reproduce")
        boundaries = _boundaries(self.calendar)
        report_boundaries = report.get("boundaries")
        if not isinstance(report_boundaries, Mapping):
            raise Phase32FinalistAuditError("development boundary report is missing")
        expected_boundary_report = {
            "selection_start": boundaries["selection_start"].isoformat(),
            "selection_end": boundaries["selection_end"].isoformat(),
            "purge_sessions": [value.isoformat() for value in boundaries["purge"]],
            "internal_start": boundaries["internal_start"].isoformat(),
            "internal_end": boundaries["internal_end"].isoformat(),
            "development_session_count": len(boundaries["sessions"]),
            "selection_session_count": len(boundaries["selection"]),
            "internal_session_count": len(boundaries["internal"]),
        }
        _assert_equivalent(expected_boundary_report, report_boundaries, label="development boundaries")
        selection_frame = frame.loc[
            (frame["decision_session"] >= boundaries["selection_start"])
            & (frame["decision_session"] <= boundaries["selection_end"])
        ].copy()
        internal_frame = frame.loc[
            (frame["decision_session"] >= boundaries["internal_start"])
            & (frame["decision_session"] <= boundaries["internal_end"])
        ].copy()
        selection_fold_map = _fold_mapping(tuple(boundaries["selection"]), PHASE32_SELECTION_FOLDS)
        internal_fold_map = _fold_mapping(tuple(boundaries["internal"]), PHASE32_INTERNAL_VALIDATION_FOLDS)
        selection_metrics: dict[str, dict[str, object]] = {}
        selection_checks: dict[str, dict[str, bool]] = {}
        for candidate in PHASE32_CANDIDATES:
            candidate_frame = selection_frame.loc[
                selection_frame["candidate_id"].astype(str).eq(candidate.candidate_id)
            ].copy()
            if not candidate_frame.empty and set(candidate_frame["direction"].astype(str)) != {candidate.direction}:
                raise Phase32FinalistAuditError(f"selection direction drifted for {candidate.candidate_id}")
            candidate_frame = _assign_fold(
                candidate_frame,
                mapping=selection_fold_map,
                field="selection_fold",
            )
            metrics = independent_metrics(
                candidate_frame,
                confidence=PHASE32_SELECTION_CONFIDENCE,
                fold_field="selection_fold",
                fold_count=PHASE32_SELECTION_FOLDS,
                label=f"selection:{candidate.candidate_id}",
            )
            selection_metrics[candidate.candidate_id] = metrics
            selection_checks[candidate.candidate_id] = _stage_checks(
                metrics,
                min_event_rows=PHASE32_SELECTION_MIN_EVENT_ROWS,
                min_signal_sessions=PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
                min_unique_instruments=PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
                min_positive_folds=PHASE32_SELECTION_MIN_POSITIVE_FOLDS,
            )
        holm = independent_holm_bonferroni(
            {
                candidate.candidate_id: float(
                    selection_metrics[candidate.candidate_id]["primary_bootstrap_p_value"]
                    if selection_metrics[candidate.candidate_id]["primary_bootstrap_p_value"] is not None
                    else 1.0
                )
                for candidate in PHASE32_CANDIDATES
            }
        )
        survivors = sorted(
            candidate.candidate_id
            for candidate in PHASE32_CANDIDATES
            if all(selection_checks[candidate.candidate_id].values())
            and bool(holm[candidate.candidate_id]["rejected_null"])
        )
        winners: list[str] = []
        for direction_name in ("LONG", "SHORT"):
            eligible = [
                candidate
                for candidate in PHASE32_CANDIDATES
                if candidate.direction == direction_name and candidate.candidate_id in survivors
            ]
            eligible.sort(
                key=lambda candidate: (
                    -float(selection_metrics[candidate.candidate_id]["primary_lcb"]),
                    candidate.candidate_id,
                )
            )
            if eligible:
                winners.append(eligible[0].candidate_id)
        internal_metrics: dict[str, dict[str, object]] = {}
        internal_checks: dict[str, dict[str, bool]] = {}
        finalists: list[str] = []
        for candidate_id in winners:
            candidate = next(item for item in PHASE32_CANDIDATES if item.candidate_id == candidate_id)
            candidate_frame = internal_frame.loc[
                internal_frame["candidate_id"].astype(str).eq(candidate_id)
            ].copy()
            if not candidate_frame.empty and set(candidate_frame["direction"].astype(str)) != {candidate.direction}:
                raise Phase32FinalistAuditError(f"internal direction drifted for {candidate_id}")
            candidate_frame = _assign_fold(
                candidate_frame,
                mapping=internal_fold_map,
                field="internal_fold",
            )
            metrics = independent_metrics(
                candidate_frame,
                confidence=PHASE32_INTERNAL_CONFIDENCE,
                fold_field="internal_fold",
                fold_count=PHASE32_INTERNAL_VALIDATION_FOLDS,
                label=f"internal:{candidate_id}",
            )
            internal_metrics[candidate_id] = metrics
            internal_checks[candidate_id] = _stage_checks(
                metrics,
                min_event_rows=PHASE32_INTERNAL_MIN_EVENT_ROWS,
                min_signal_sessions=PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
                min_unique_instruments=PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
                min_positive_folds=PHASE32_INTERNAL_MIN_POSITIVE_FOLDS,
            )
            if all(internal_checks[candidate_id].values()):
                finalists.append(candidate_id)
        if tuple(survivors) != PHASE32_EXPECTED_SELECTION_SURVIVORS:
            raise Phase32FinalistAuditError("independent selection survivor set differs from accepted development result")
        if tuple(winners) != PHASE32_EXPECTED_SELECTION_WINNERS:
            raise Phase32FinalistAuditError("independent selection winners differ from accepted development result")
        if tuple(finalists) != PHASE32_EXPECTED_FINALISTS:
            raise Phase32FinalistAuditError("independent finalist set differs from accepted development result")
        if report.get("selection_survivor_ids") != survivors:
            raise Phase32FinalistAuditError("development report selection survivors differ from independent audit")
        if report.get("selection_winner_ids") != winners:
            raise Phase32FinalistAuditError("development report selection winners differ from independent audit")
        if report.get("finalist_ids") != finalists:
            raise Phase32FinalistAuditError("development report finalists differ from independent audit")
        report_selection_metrics = report.get("selection_metrics")
        report_selection_checks = report.get("selection_checks")
        report_holm = report.get("holm_bonferroni")
        report_internal_metrics = report.get("internal_metrics")
        report_internal_checks = report.get("internal_checks")
        if not all(isinstance(value, Mapping) for value in (
            report_selection_metrics,
            report_selection_checks,
            report_holm,
            report_internal_metrics,
            report_internal_checks,
        )):
            raise Phase32FinalistAuditError("development report metric structures are incomplete")
        metric_fields = tuple(next(iter(selection_metrics.values())).keys())
        for candidate_id, metrics in selection_metrics.items():
            expected = {key: report_selection_metrics[candidate_id][key] for key in metric_fields}
            _assert_equivalent(metrics, expected, label=f"selection metrics {candidate_id}")
            _assert_equivalent(
                selection_checks[candidate_id],
                report_selection_checks[candidate_id],
                label=f"selection checks {candidate_id}",
            )
        _assert_equivalent(holm, report_holm, label="Holm family")
        for candidate_id, metrics in internal_metrics.items():
            expected = {key: report_internal_metrics[candidate_id][key] for key in metric_fields}
            _assert_equivalent(metrics, expected, label=f"internal metrics {candidate_id}")
            _assert_equivalent(
                internal_checks[candidate_id],
                report_internal_checks[candidate_id],
                label=f"internal checks {candidate_id}",
            )
        return {
            "selection_survivor_ids": survivors,
            "selection_winner_ids": winners,
            "finalist_ids": finalists,
            "selection_metrics": selection_metrics,
            "selection_checks": selection_checks,
            "holm_bonferroni": holm,
            "internal_metrics": internal_metrics,
            "internal_checks": internal_checks,
        }

    def _build_protected_plan(self, finalist_ids: tuple[str, ...]) -> tuple[dict[str, object], list[dict[str, object]]]:
        acceptance = _read_json(
            self.acceptance_path,
            label="Phase32 independent predictor/source acceptance",
        )
        if acceptance.get("contract_version") != PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT:
            raise Phase32FinalistAuditError("independent predictor/source acceptance contract drifted")
        if acceptance.get("pass") is not True:
            raise Phase32FinalistAuditError("independent predictor/source acceptance is not PASS")
        if acceptance.get("acceptance_fingerprint") != PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT:
            raise Phase32FinalistAuditError("independent predictor/source fingerprint drifted")
        if not self.predictor_path.is_file() or sha256_file(self.predictor_path) != PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256:
            raise Phase32FinalistAuditError("frozen predictor artifact SHA drifted")
        if not self.filing_entity_path.is_file() or sha256_file(self.filing_entity_path) != PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256:
            raise Phase32FinalistAuditError("frozen filing-entity evidence SHA drifted")
        predictors = _read_jsonl(self.predictor_path, label="Phase32 frozen predictors")
        filing_rows = _read_jsonl(self.filing_entity_path, label="Phase32 filing-entity evidence")
        protected_predictors = [
            row for row in predictors if str(row.get("stage") or "") == "protected_predictor_only"
        ]
        if len(protected_predictors) != 973:
            raise Phase32FinalistAuditError("protected predictor partition count drifted")
        finalist_set = set(finalist_ids)
        finalist_predictors = [
            row for row in protected_predictors if str(row.get("candidate_id") or "") in finalist_set
        ]
        if not finalist_predictors:
            raise Phase32FinalistAuditError("frozen finalist has no protected predictor rows")
        for row in protected_predictors:
            if row.get("policy_fingerprint") != PHASE32_FROZEN_POLICY_FINGERPRINT:
                raise Phase32FinalistAuditError("protected predictor policy fingerprint drifted")
            if int(row.get("outcome_rows_read", -1)) != 0:
                raise Phase32FinalistAuditError("protected predictor reports an outcome read")
            forbidden = _FORBIDDEN_PREDICTOR_OUTCOME_FIELDS.intersection(row)
            if forbidden:
                raise Phase32FinalistAuditError(
                    "protected predictor contains forbidden outcome fields: " + ", ".join(sorted(forbidden))
                )
        execution = resolve_protected_execution_tickers(
            protected_predictors,
            filing_rows,
            finalist_ids=finalist_ids,
        )
        protected_sessions = tuple(
            self.calendar.sessions_in_range(
                date.fromisoformat(PHASE32_PROTECTED_START),
                date.fromisoformat(PHASE32_PROTECTED_LAST_SIGNAL),
            )
        )
        if not protected_sessions:
            raise Phase32FinalistAuditError("protected XNYS session grid is empty")
        fold_map = _fold_mapping(protected_sessions, PHASE32_PROTECTED_FOLDS)
        candidate_by_id = {candidate.candidate_id: candidate for candidate in PHASE32_CANDIDATES}
        plan_rows: list[dict[str, object]] = []
        for predictor in finalist_predictors:
            candidate_id = str(predictor.get("candidate_id") or "")
            candidate = candidate_by_id[candidate_id]
            if str(predictor.get("direction") or "") != candidate.direction:
                raise Phase32FinalistAuditError("protected finalist direction drifted")
            decision_session = date.fromisoformat(str(predictor.get("decision_session") or ""))
            exit_session = date.fromisoformat(str(predictor.get("exit_session") or ""))
            if not (
                date.fromisoformat(PHASE32_PROTECTED_START)
                <= decision_session
                <= date.fromisoformat(PHASE32_PROTECTED_LAST_SIGNAL)
            ):
                raise Phase32FinalistAuditError("protected finalist predictor decision session is outside frozen window")
            if exit_session <= decision_session or exit_session > date.fromisoformat(PHASE32_PROTECTED_OUTCOME_END):
                raise Phase32FinalistAuditError("protected finalist predictor exit is outside frozen outcome window")
            key = (
                str(predictor.get("instrument_id") or ""),
                decision_session.isoformat(),
                candidate_id,
            )
            ticker = execution.get(key)
            if not ticker:
                raise Phase32FinalistAuditError("protected finalist predictor lacks exact execution ticker")
            provider_tickers = {str(value) for value in predictor.get("provider_tickers") or []}
            if ticker not in provider_tickers:
                raise Phase32FinalistAuditError("protected execution ticker is absent from frozen provider lineage")
            plan_row = {
                "candidate_id": candidate_id,
                "direction": candidate.direction,
                "instrument_id": str(predictor.get("instrument_id") or ""),
                "identity_key": predictor.get("identity_key"),
                "identity_quality": str(predictor.get("identity_quality") or ""),
                "issuer_cik": str(predictor.get("issuer_cik") or ""),
                "decision_session": decision_session.isoformat(),
                "exit_session": exit_session.isoformat(),
                "execution_ticker": ticker,
                "protected_fold": int(fold_map[decision_session]),
                "predictor_row_sha256": _sha256_text(_canonical_json(predictor)),
                "policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            }
            if any(field in plan_row for field in _PLAN_FORBIDDEN_FIELDS):
                raise Phase32FinalistAuditError("protected plan row contains a forbidden outcome field")
            plan_rows.append(plan_row)
        plan_rows.sort(
            key=lambda row: (
                str(row["decision_session"]),
                str(row["instrument_id"]),
                str(row["candidate_id"]),
            )
        )
        if len({(row["instrument_id"], row["decision_session"], row["candidate_id"]) for row in plan_rows}) != len(plan_rows):
            raise Phase32FinalistAuditError("protected plan duplicates the frozen event unit")
        source_gate = protected_source_sample_gate(plan_rows)
        fold_counts = {
            str(fold): sum(int(row["protected_fold"]) == fold for row in plan_rows)
            for fold in range(PHASE32_PROTECTED_FOLDS)
        }
        _write_jsonl(self.protected_plan_rows_path(), plan_rows)
        plan_rows_sha = sha256_file(self.protected_plan_rows_path())
        plan_core: dict[str, object] = {
            "contract_version": PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
            "phase32_policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            "independent_acceptance_fingerprint": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
            "predictor_sha256": PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
            "filing_entity_evidence_sha256": PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
            "finalist_ids": list(finalist_ids),
            "protected_signal_start": PHASE32_PROTECTED_START,
            "protected_last_signal": PHASE32_PROTECTED_LAST_SIGNAL,
            "protected_outcome_end": PHASE32_PROTECTED_OUTCOME_END,
            "protected_folds": PHASE32_PROTECTED_FOLDS,
            "protected_fold_row_counts": fold_counts,
            "protected_plan_rows": len(plan_rows),
            "protected_plan_rows_sha256": plan_rows_sha,
            "source_only_sample_gate": source_gate,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
        }
        plan_fingerprint = _sha256_text(_canonical_json(plan_core))
        plan = {
            **plan_core,
            "plan_fingerprint": plan_fingerprint,
            "pass": True,
        }
        self.protected_plan_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.protected_plan_path(),
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
        )
        return plan, plan_rows

    def run(self) -> dict[str, object]:
        if phase32_policy_fingerprint() != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32FinalistAuditError("Phase32 scientific policy fingerprint drifted")
        if PHASE32_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_5":
            raise Phase32FinalistAuditError("Phase32 global multiplicity contract drifted")
        if PHASE32_SELECTION_WINNER_RULE != "highest_primary_selection_LCB_then_candidate_id":
            raise Phase32FinalistAuditError("Phase32 selection winner rule drifted")
        if PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED:
            raise Phase32FinalistAuditError("Phase32 runner-up substitution became enabled")
        report, finalists_artifact, outcomes = self._verify_development_artifacts()
        recomputed = self._recompute_development(outcomes, report)
        finalists = tuple(str(value) for value in recomputed["finalist_ids"])
        if tuple(finalists_artifact.get("finalist_ids") or []) != finalists:
            raise Phase32FinalistAuditError("finalist artifact differs from independent recomputation")
        plan, plan_rows = self._build_protected_plan(finalists)
        source_gate = plan["source_only_sample_gate"]
        protected_return_authorized = bool(source_gate["possible"])
        audit_core: dict[str, object] = {
            "contract_version": PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "phase32_policy_fingerprint": PHASE32_FROZEN_POLICY_FINGERPRINT,
            "independent_acceptance_fingerprint": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
            "development_report_sha256": sha256_file(self.development_root / "development_study.json"),
            "development_outcomes_sha256": report["development_outcomes_sha256"],
            "development_signals_sha256": report["development_signals_sha256"],
            "development_finalists_sha256": report["finalists_sha256"],
            "selection_survivor_ids": recomputed["selection_survivor_ids"],
            "selection_winner_ids": recomputed["selection_winner_ids"],
            "finalist_ids": list(finalists),
            "protected_plan_fingerprint": plan["plan_fingerprint"],
            "protected_plan_sha256": sha256_file(self.protected_plan_path()),
            "protected_plan_rows_sha256": plan["protected_plan_rows_sha256"],
            "protected_plan_rows": len(plan_rows),
            "protected_source_only_sample_gate": source_gate,
            "protected_return_authorized_after_fingerprint_freeze": protected_return_authorized,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
        }
        audit_fingerprint = _sha256_text(_canonical_json(audit_core))
        audit = {
            **audit_core,
            "audit_fingerprint": audit_fingerprint,
            "status": (
                "AUDIT_PASS_PROTECTED_PLAN_READY"
                if protected_return_authorized
                else "AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE"
            ),
            "pass": True,
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path(),
            json.dumps(audit, indent=2, sort_keys=True) + "\n",
        )
        return audit
