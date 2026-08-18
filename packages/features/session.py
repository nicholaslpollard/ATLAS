from __future__ import annotations

import numpy as np
import pandas as pd

from packages.features.gaps import gap_return


REQUIRED_SESSION_COLUMNS = (
    "symbol",
    "timestamp_utc",
    "session_date",
    "session_segment",
    "open",
    "high",
    "low",
    "close",
)


def regular_session_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute regular-session context without leaking across symbols or sessions.

    Non-regular rows are retained in the output index but receive missing session
    feature values. Previous-session-close state is carried only between completed
    regular sessions for the same exact provider-native symbol.
    """

    missing = [column for column in REQUIRED_SESSION_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"session feature input is missing required columns: {', '.join(missing)}")

    ordered = frame.copy()
    ordered["symbol"] = ordered["symbol"].astype("string").str.strip()
    ordered["timestamp_utc"] = pd.to_datetime(ordered["timestamp_utc"], utc=True, errors="raise")
    ordered["session_date"] = pd.to_datetime(ordered["session_date"], errors="raise").dt.date
    for column in ("open", "high", "low", "close"):
        ordered[column] = pd.to_numeric(ordered[column], errors="coerce").astype("float64")

    output = pd.DataFrame(index=ordered.index)
    output["session_bar_index"] = pd.Series(pd.NA, index=ordered.index, dtype="Int32")
    for column in (
        "session_open",
        "previous_session_close",
        "overnight_gap",
        "session_return_from_open",
        "session_high_to_date",
        "session_low_to_date",
        "session_range_position_to_date",
    ):
        output[column] = np.nan

    regular_mask = ordered["session_segment"].astype("string") == "regular"
    regular = ordered.loc[regular_mask].sort_values(["symbol", "session_date", "timestamp_utc"], kind="stable")
    if regular.empty:
        return output

    for symbol, symbol_rows in regular.groupby("symbol", sort=False, observed=True):
        previous_close: float | None = None
        for _, session_rows in symbol_rows.groupby("session_date", sort=True, observed=True):
            session_rows = session_rows.sort_values("timestamp_utc", kind="stable")
            idx = session_rows.index
            session_open = float(session_rows.iloc[0]["open"])
            session_close = float(session_rows.iloc[-1]["close"])
            highs = session_rows["high"].cummax()
            lows = session_rows["low"].cummin()
            width = highs - lows

            output.loc[idx, "session_bar_index"] = pd.array(range(len(idx)), dtype="Int32")
            output.loc[idx, "session_open"] = session_open
            output.loc[idx, "session_return_from_open"] = session_rows["close"] / session_open - 1.0
            output.loc[idx, "session_high_to_date"] = highs
            output.loc[idx, "session_low_to_date"] = lows
            position = ((session_rows["close"] - lows) / width).where(width != 0.0, 0.5)
            output.loc[idx, "session_range_position_to_date"] = position

            if previous_close is not None:
                previous_series = pd.Series(previous_close, index=idx, dtype="float64")
                open_series = pd.Series(session_open, index=idx, dtype="float64")
                output.loc[idx, "previous_session_close"] = previous_close
                output.loc[idx, "overnight_gap"] = gap_return(open_series, previous_series)
            previous_close = session_close

    return output
