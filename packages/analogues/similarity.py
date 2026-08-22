from __future__ import annotations

import math
from datetime import date

import pandas as pd

from packages.analogues.policy import (
    PHASE12_ANALOGUE_TOP_K,
    PHASE12_DISTANCE_METRIC,
    PHASE12_PER_INSTRUMENT_CAP,
    PHASE12_SIMILARITY_FEATURES,
)
from packages.data.sql import sql_string


class AnalogueSimilarityError(ValueError):
    pass


def _number(value: float) -> str:
    resolved = float(value)
    if not math.isfinite(resolved):
        raise AnalogueSimilarityError("current similarity features must be finite")
    return repr(resolved)


def _feature_eligibility(alias: str = "h") -> str:
    clauses = [f'isfinite(CAST({alias}."{name}" AS DOUBLE))' for name in PHASE12_SIMILARITY_FEATURES]
    return " AND ".join(clauses)


def _market_clause(market_state: str | None, alias: str = "h") -> str:
    if market_state is None or not str(market_state).strip():
        return ""
    return (
        f" AND {alias}.market_regime_available = TRUE"
        f" AND {alias}.market_regime_composite = {sql_string(str(market_state).strip())}"
    )


def analogue_selection_sql(
    *,
    source_sql: str,
    as_of_date: date,
    market_state: str | None,
    current_features: dict[str, float],
) -> str:
    if tuple(current_features) != PHASE12_SIMILARITY_FEATURES:
        if set(current_features) != set(PHASE12_SIMILARITY_FEATURES):
            raise AnalogueSimilarityError("current feature vector does not match Phase 12 policy")
    current = {name: _number(current_features[name]) for name in PHASE12_SIMILARITY_FEATURES}
    stats = []
    distance_terms = []
    for name in PHASE12_SIMILARITY_FEATURES:
        stats.append(f'AVG(CAST("{name}" AS DOUBLE)) AS "mean__{name}"')
        stats.append(f'STDDEV_POP(CAST("{name}" AS DOUBLE)) AS "std__{name}"')
        distance_terms.append(
            "CASE WHEN s.\"std__{0}\" IS NULL OR s.\"std__{0}\" = 0.0 "
            "THEN 0.0 ELSE POW((CAST(h.\"{0}\" AS DOUBLE) - {1}) / s.\"std__{0}\", 2) END".format(
                name, current[name]
            )
        )
    distance_sum = " + ".join(distance_terms)
    as_of = sql_string(as_of_date.isoformat())
    market = _market_clause(market_state)
    selected_features = ",\n                    ".join(f'h."{name}"' for name in PHASE12_SIMILARITY_FEATURES)
    return f"""
        WITH eligible AS (
            SELECT *
            FROM {source_sql} AS h
            WHERE h.session_date < CAST({as_of} AS DATE)
              AND h.future_date < CAST({as_of} AS DATE)
              AND isfinite(CAST(h.forward_return AS DOUBLE))
              AND {_feature_eligibility('h')}
              {market}
        ),
        stats AS (
            SELECT
                COUNT(*) AS eligible_pool_rows,
                {', '.join(stats)}
            FROM eligible
        ),
        scored AS (
            SELECT
                h.observation_key,
                h.session_date,
                h.symbol,
                h.instrument_id,
                h.observation_close,
                h.future_date,
                h.future_close,
                h.forward_return,
                h.market_regime_available,
                h.market_regime_composite,
                {selected_features},
                s.eligible_pool_rows,
                SQRT(({distance_sum}) / {len(PHASE12_SIMILARITY_FEATURES)}) AS distance
            FROM eligible AS h
            CROSS JOIN stats AS s
        ),
        capped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY instrument_id
                    ORDER BY distance ASC, session_date DESC, observation_key ASC
                ) AS instrument_similarity_rank
            FROM scored
        )
        SELECT *
        FROM capped
        WHERE instrument_similarity_rank <= {PHASE12_PER_INSTRUMENT_CAP}
        ORDER BY distance ASC, session_date DESC, observation_key ASC
        LIMIT {PHASE12_ANALOGUE_TOP_K}
    """


def select_analogues(
    connection: object,
    *,
    source_sql: str,
    as_of_date: date,
    market_state: str | None,
    current_features: dict[str, float],
) -> tuple[pd.DataFrame, int]:
    sql = analogue_selection_sql(
        source_sql=source_sql,
        as_of_date=as_of_date,
        market_state=market_state,
        current_features=current_features,
    )
    frame = connection.execute(sql).fetch_df()  # type: ignore[attr-defined]
    if frame.empty:
        return frame, 0
    pool_rows = int(frame["eligible_pool_rows"].iloc[0])
    if (frame["distance"] < 0.0).any() or not frame["distance"].map(math.isfinite).all():
        raise AnalogueSimilarityError("selected analogue distances are invalid")
    if frame["observation_key"].duplicated().any():
        raise AnalogueSimilarityError("selected analogue observation keys are duplicated")
    if int(frame.groupby("instrument_id").size().max()) > PHASE12_PER_INSTRUMENT_CAP:
        raise AnalogueSimilarityError("selected analogues violate the per-instrument cap")
    ordered = frame.sort_values(
        ["distance", "session_date", "observation_key"],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)
    if not ordered["observation_key"].equals(frame.reset_index(drop=True)["observation_key"]):
        raise AnalogueSimilarityError(f"analogue query violated {PHASE12_DISTANCE_METRIC} ordering")
    return frame.drop(columns=["eligible_pool_rows"]), pool_rows
