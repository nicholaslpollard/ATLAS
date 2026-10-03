from __future__ import annotations

"""Read-only ThetaData Python-library adapter.

ThetaData's Python library connects directly to ThetaData over HTTPS/gRPC and does
not require Theta Terminal or Java. ATLAS uses pandas DataFrames because pandas is
already a core dependency.

The adapter converts provider DataFrames to deterministic Python records and canonical
JSON bytes for immutable evidence receipts. These bytes are a canonical serialization
of the provider DataFrame, not raw network/wire bytes.
"""

from dataclasses import dataclass
from datetime import date, datetime
import importlib.metadata
import json
import math
import sys
import threading
import time
from typing import Any, Callable, Mapping, Sequence

MIN_PYTHON = (3, 12)
MIN_API_KEY_LIBRARY = (1, 0, 9)
TARGET_LIBRARY_VERSION = "1.0.12"
TRANSPORT = "THETADATA_PYTHON_LIBRARY_GRPC"


class ThetaDataError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


@dataclass(frozen=True, slots=True)
class ThetaDataResponse:
    # Kept for compatibility with the existing source qualification/cache contracts.
    # The Python library does not expose HTTP status or headers.
    http_status: int
    rows: tuple[dict[str, Any], ...]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float
    raw_body: bytes
    transport: str = TRANSPORT
    library_version: str | None = None
    evidence_encoding: str = "CANONICAL_PROVIDER_DATAFRAME_JSON"


_thread_state = threading.local()


def _version_tuple(value: str) -> tuple[int, ...]:
    pieces: list[int] = []
    for token in value.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if not digits:
            break
        pieces.append(int(digits))
    return tuple(pieces)


def installed_library_version() -> str | None:
    try:
        return importlib.metadata.version("thetadata")
    except importlib.metadata.PackageNotFoundError:
        return None


def python_runtime_supported() -> bool:
    return sys.version_info[:2] >= MIN_PYTHON


def _load_theta_client_class():
    if not python_runtime_supported():
        raise ThetaDataError(
            "ThetaData Python library requires Python 3.12 or newer"
        )
    version = installed_library_version()
    if version is None:
        raise ThetaDataError(
            "ThetaData Python library is not installed; install the optional "
            "ATLAS ThetaData provider dependency after subscription setup"
        )
    if _version_tuple(version) < MIN_API_KEY_LIBRARY:
        raise ThetaDataError(
            "ThetaData Python library is too old for the supported API-key flow"
        )
    try:
        from thetadata import ThetaClient
    except Exception as exc:  # provider import contract is external
        raise ThetaDataError(
            f"ThetaData Python library import failed: {type(exc).__name__}"
        ) from exc
    return ThetaClient, version


def _client():
    cached = getattr(_thread_state, "client", None)
    if cached is not None:
        return cached
    client_class, version = _load_theta_client_class()
    try:
        client = client_class(dataframe_type="pandas")
    except Exception as exc:
        raise ThetaDataError(
            f"ThetaData client authentication/initialization failed: "
            f"{type(exc).__name__}"
        ) from exc
    _thread_state.client = client
    _thread_state.library_version = version
    return client


def reset_thread_client_for_tests() -> None:
    for name in ("client", "library_version"):
        if hasattr(_thread_state, name):
            delattr(_thread_state, name)


def _json_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ThetaDataError("ThetaData DataFrame contains non-finite float")
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_scalar(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    raise ThetaDataError(
        f"ThetaData DataFrame contains unsupported scalar type {type(value).__name__}"
    )


def _records_from_dataframe(frame: Any) -> tuple[dict[str, Any], ...]:
    if hasattr(frame, "to_dict"):
        try:
            records = frame.to_dict(orient="records")
        except TypeError:
            records = None
        if isinstance(records, list):
            return tuple(
                {str(key): _json_scalar(value) for key, value in row.items()}
                for row in records
            )
    if hasattr(frame, "to_dicts"):
        records = frame.to_dicts()
        if isinstance(records, list):
            return tuple(
                {str(key): _json_scalar(value) for key, value in row.items()}
                for row in records
            )
    raise ThetaDataError(
        "ThetaData Python library returned an unsupported DataFrame object"
    )


def _canonical_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return (
        json.dumps(
            list(rows),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _call(method_name: str, **kwargs: Any) -> ThetaDataResponse:
    client = _client()
    method = getattr(client, method_name, None)
    if method is None or not callable(method):
        raise ThetaDataError(
            f"ThetaData Python library missing method {method_name}"
        )
    started = time.perf_counter()
    try:
        frame = method(**kwargs)
    except Exception as exc:
        # Avoid echoing an external exception message because a provider/auth library
        # may include sensitive request context. The class is enough for diagnosis.
        raise ThetaDataError(
            f"ThetaData Python library call {method_name} failed: "
            f"{type(exc).__name__}"
        ) from exc
    rows = _records_from_dataframe(frame)
    canonical = _canonical_bytes(rows)
    version = getattr(_thread_state, "library_version", installed_library_version())
    return ThetaDataResponse(
        http_status=200,
        rows=rows,
        headers={
            "atlas-provider-transport": TRANSPORT,
            "atlas-provider-method": method_name,
        },
        response_bytes=len(canonical),
        elapsed_seconds=max(0.0, time.perf_counter() - started),
        raw_body=canonical,
        library_version=version,
    )


def _day(value: str) -> date:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def option_at_time_quote_surface(
    *,
    symbol: str,
    date_et: str,
    time_of_day_et: str,
    right: str = "call",
    max_dte: int = 75,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Return all CALL quote candidates known at one causal decision clock."""
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    day = _day(date_et)
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "start_date": day,
        "end_date": day,
        "time_of_day": time_of_day_et,
        "expiration": "*",
        "strike": "*",
        "right": right,
        "max_dte": max_dte,
    }
    if strike_range is not None:
        kwargs["strike_range"] = strike_range
    return _call("option_at_time_quote", **kwargs)


def option_at_time_quote(
    *,
    symbol: str,
    expiration: str,
    strike: str,
    right: str,
    date_et: str,
    time_of_day_et: str,
) -> ThetaDataResponse:
    """Exact-contract at-time quote reserved for selected-contract exit evidence."""
    day = _day(date_et)
    return _call(
        "option_at_time_quote",
        symbol=symbol,
        start_date=day,
        end_date=day,
        time_of_day=time_of_day_et,
        expiration=_day(expiration),
        strike=str(strike),
        right=right,
    )


def option_history_open_interest_surface(
    *,
    symbol: str,
    date_et: str,
    right: str = "call",
    max_dte: int = 75,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Historical previous-session open interest for a bounded option surface."""
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "date": _day(date_et),
        "expiration": "*",
        "strike": "*",
        "right": right,
        "max_dte": max_dte,
    }
    if strike_range is not None:
        kwargs["strike_range"] = strike_range
    return _call("option_history_open_interest", **kwargs)


def option_history_binomial_first_order_greeks_at_minute(
    *,
    symbol: str,
    expiration: str,
    date_et: str,
    right: str = "call",
    time_of_day_et: str = "09:35:00.000",
    annual_dividend: float,
    rate_type: str = "sofr",
    version: str = "1",
    binomial_steps: int = 101,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    """Dividend-aware American-style first-order Greeks at one historical minute."""
    if annual_dividend < 0:
        raise ValueError("annual_dividend cannot be negative")
    if binomial_steps < 5 or binomial_steps > 201:
        raise ValueError("binomial_steps must be in [5, 201]")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    if version not in {"1", "latest"}:
        raise ValueError("unsupported ThetaData Greeks version")
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "expiration": _day(expiration),
        "strike": "*",
        "right": right,
        "date": _day(date_et),
        "start_time": time_of_day_et,
        "end_time": time_of_day_et,
        "interval": "1m",
        "annual_dividend": float(annual_dividend),
        "rate_type": rate_type,
        "version": version,
        "binomial_steps": binomial_steps,
    }
    if strike_range is not None:
        kwargs["strike_range"] = strike_range
    return _call("option_history_binomial_greeks_first_order", **kwargs)
