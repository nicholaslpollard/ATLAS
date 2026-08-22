from __future__ import annotations

import math

import pandas as pd

from packages.schemas.discovery_score import DiscoveryDirection


class AnalogueOutcomeError(ValueError):
    pass


def direction_sign(direction: DiscoveryDirection | str) -> float:
    value = direction.value if isinstance(direction, DiscoveryDirection) else str(direction)
    if value == DiscoveryDirection.BULLISH.value:
        return 1.0
    if value == DiscoveryDirection.BEARISH.value:
        return -1.0
    raise AnalogueOutcomeError("Phase 12 requires a bullish or bearish promoted candidate")


def attach_direction_adjusted_returns(
    frame: pd.DataFrame,
    *,
    direction: DiscoveryDirection | str,
) -> pd.DataFrame:
    if "forward_return" not in frame.columns:
        raise AnalogueOutcomeError("analogue frame is missing forward_return")
    result = frame.copy()
    sign = direction_sign(direction)
    result["direction_adjusted_return"] = (
        pd.to_numeric(result["forward_return"], errors="raise").astype("float64") * sign
    )
    if not result["direction_adjusted_return"].map(math.isfinite).all():
        raise AnalogueOutcomeError("direction-adjusted analogue returns must be finite")
    return result


def extract_directional_paths(
    connection: object,
    *,
    source_sql: str,
    analogue_frame: pd.DataFrame,
    direction: DiscoveryDirection | str,
) -> pd.DataFrame:
    if analogue_frame.empty:
        return pd.DataFrame(
            columns=(
                "observation_key",
                "instrument_id",
                "session_date",
                "direction_return_1",
                "direction_return_2",
                "direction_return_3",
            )
        )
    required = {
        "observation_key",
        "instrument_id",
        "session_date",
        "future_date",
        "observation_close",
        "future_close",
        "forward_return",
    }
    missing = sorted(required.difference(analogue_frame.columns))
    if missing:
        raise AnalogueOutcomeError("analogue path input missing columns: " + ", ".join(missing))

    selected = analogue_frame[
        [
            "observation_key",
            "instrument_id",
            "session_date",
            "future_date",
            "observation_close",
            "future_close",
            "forward_return",
        ]
    ].copy()
    connection.register("phase12_selected_analogues", selected)  # type: ignore[attr-defined]
    sql = f"""
        WITH calendar_days AS (
            SELECT DISTINCT session_date
            FROM {source_sql}
            WHERE session_date >= (SELECT MIN(session_date) FROM phase12_selected_analogues)
              AND session_date <= (SELECT MAX(future_date) FROM phase12_selected_analogues)
        ),
        calendar AS (
            SELECT
                session_date,
                LEAD(session_date, 1) OVER (ORDER BY session_date) AS session_1,
                LEAD(session_date, 2) OVER (ORDER BY session_date) AS session_2,
                LEAD(session_date, 3) OVER (ORDER BY session_date) AS session_3
            FROM calendar_days
        ),
        selected_instruments AS (
            SELECT DISTINCT instrument_id FROM phase12_selected_analogues
        ),
        history AS (
            SELECT h.instrument_id, h.session_date, h.observation_close
            FROM {source_sql} AS h
            INNER JOIN selected_instruments AS i USING (instrument_id)
            WHERE h.session_date >= (SELECT MIN(session_date) FROM phase12_selected_analogues)
              AND h.session_date <= (SELECT MAX(future_date) FROM phase12_selected_analogues)
        )
        SELECT
            a.observation_key,
            a.instrument_id,
            a.session_date,
            a.future_date,
            a.observation_close,
            a.future_close,
            a.forward_return,
            h1.observation_close AS close_1,
            h2.observation_close AS close_2,
            h3.observation_close AS close_3
        FROM phase12_selected_analogues AS a
        INNER JOIN calendar AS c ON c.session_date = a.session_date
        INNER JOIN history AS h1
          ON h1.instrument_id = a.instrument_id AND h1.session_date = c.session_1
        INNER JOIN history AS h2
          ON h2.instrument_id = a.instrument_id AND h2.session_date = c.session_2
        INNER JOIN history AS h3
          ON h3.instrument_id = a.instrument_id AND h3.session_date = c.session_3
        WHERE c.session_3 = a.future_date
        ORDER BY a.observation_key
    """
    result = connection.execute(sql).fetch_df()  # type: ignore[attr-defined]
    if result.empty:
        return pd.DataFrame(
            columns=(
                "observation_key",
                "instrument_id",
                "session_date",
                "direction_return_1",
                "direction_return_2",
                "direction_return_3",
            )
        )
    sign = direction_sign(direction)
    for horizon in (1, 2, 3):
        result[f"direction_return_{horizon}"] = (
            result[f"close_{horizon}"].astype("float64") / result["observation_close"].astype("float64")
            - 1.0
        ) * sign
    raw_terminal = result["close_3"].astype("float64") / result["observation_close"].astype("float64") - 1.0
    endpoint_delta = (raw_terminal - result["forward_return"].astype("float64")).abs()
    future_close_delta = (result["close_3"].astype("float64") - result["future_close"].astype("float64")).abs()
    tolerance = 1e-10
    if (endpoint_delta > tolerance).any() or (future_close_delta > tolerance).any():
        raise AnalogueOutcomeError("three-session path endpoint does not reproduce accepted outcome evidence")
    columns = [
        "observation_key",
        "instrument_id",
        "session_date",
        "direction_return_1",
        "direction_return_2",
        "direction_return_3",
    ]
    path = result[columns].copy()
    if path["observation_key"].duplicated().any():
        raise AnalogueOutcomeError("path evidence contains duplicate observation keys")
    for column in ("direction_return_1", "direction_return_2", "direction_return_3"):
        if not path[column].map(math.isfinite).all():
            raise AnalogueOutcomeError("path evidence contains non-finite returns")
    return path.reset_index(drop=True)
