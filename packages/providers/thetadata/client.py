from __future__ import annotations

"""Read-only ThetaData adapter backed by an isolated Python-library worker.

ThetaData 1.0.12 requires protobuf>=6.32.1 while the accepted ATLAS Webull SDK
requires protobuf<6 on Python>=3.12. To avoid destabilizing broker/runtime code,
ThetaData runs in a dedicated provider virtual environment and ATLAS communicates
with persistent worker processes over line-delimited JSON on stdin/stdout.

No Theta Terminal or Java is involved.
"""

import atexit
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any, Mapping, Sequence
import uuid


ROOT = Path(__file__).resolve().parents[3]
WORKER_SCRIPT = ROOT / "scripts" / "thetadata_python_worker_v1.py"
THETADATA_PYTHON_ENV = "ATLAS_THETADATA_PYTHON"
DEFAULT_PROVIDER_VENV = ROOT / ".provider_venvs" / "thetadata"
TARGET_LIBRARY_VERSION = "1.0.12"
MIN_PROVIDER_PYTHON = (3, 12)
TRANSPORT = "THETADATA_PYTHON_LIBRARY_ISOLATED_WORKER"
EVIDENCE_ENCODING = "CANONICAL_PROVIDER_DATAFRAME_JSON"
WORKER_RESPONSE_TIMEOUT_SECONDS = 180.0


class ThetaDataError(RuntimeError):
    def __init__(
        self, message: str, *, http_status: int | None = None,
        provider_error_type: str | None = None,
        provider_grpc_status: str | None = None,
        provider_error_stage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        # Sanitized, bounded provider metadata. Never store raw SDK messages.
        self.provider_error_type = provider_error_type
        self.provider_grpc_status = provider_grpc_status
        # Only one of three fixed internal processing stages, never SDK text.
        self.provider_error_stage = (
            provider_error_stage
            if provider_error_stage in {
                "ARGUMENT_CONVERSION", "SDK_QUOTE_CALL",
                "DATAFRAME_SERIALIZATION",
            } else None
        )


@dataclass(frozen=True, slots=True)
class ThetaDataResponse:
    # http_status/headers remain for compatibility with existing qualification code.
    # The worker/library transport does not expose HTTP response metadata.
    http_status: int
    rows: tuple[dict[str, Any], ...]
    headers: dict[str, str]
    response_bytes: int
    elapsed_seconds: float
    raw_body: bytes
    transport: str = TRANSPORT
    library_version: str | None = None
    provider_environment_fingerprint: str | None = None
    evidence_encoding: str = EVIDENCE_ENCODING
    explicit_no_data: bool = False


_thread_state = threading.local()
_workers_lock = threading.Lock()
_workers: set["_Worker"] = set()


def provider_python_path() -> Path:
    override = str(os.environ.get(THETADATA_PYTHON_ENV, "")).strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return DEFAULT_PROVIDER_VENV / "Scripts" / "python.exe"
    return DEFAULT_PROVIDER_VENV / "bin" / "python"


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


class _Worker:
    def __init__(self, python_path: Path) -> None:
        if not python_path.is_file():
            raise ThetaDataError(
                "isolated ThetaData provider Python is unavailable; run the provider "
                "environment setup after the ThetaData subscription is ready"
            )
        if not WORKER_SCRIPT.is_file():
            raise ThetaDataError("ThetaData provider worker script is unavailable")
        try:
            self.process = subprocess.Popen(
                [str(python_path), str(WORKER_SCRIPT), "--serve"],
                cwd=str(ROOT),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=os.environ.copy(),
            )
        except OSError as exc:
            raise ThetaDataError(
                f"unable to start isolated ThetaData provider worker: "
                f"{type(exc).__name__}"
            ) from exc
        if self.process.stdin is None or self.process.stdout is None:
            self.close()
            raise ThetaDataError("ThetaData provider worker pipes unavailable")

        self._responses: queue.Queue[str | None] = queue.Queue()
        self._request_lock = threading.Lock()
        self._reader = threading.Thread(
            target=self._read_stdout,
            name="atlas-thetadata-worker-reader",
            daemon=True,
        )
        self._reader.start()
        with _workers_lock:
            _workers.add(self)

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def request(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        with self._request_lock:
            if self.process.poll() is not None:
                raise ThetaDataError("ThetaData provider worker exited unexpectedly")
            request_id = uuid.uuid4().hex
            payload = {
                "id": request_id,
                "method": method,
                "kwargs": kwargs,
            }
            assert self.process.stdin is not None
            try:
                self.process.stdin.write(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
                )
                self.process.stdin.flush()
                line = self._responses.get(timeout=WORKER_RESPONSE_TIMEOUT_SECONDS)
            except queue.Empty as exc:
                self.close()
                raise ThetaDataError(
                    "ThetaData provider worker timed out waiting for a response"
                ) from exc
            except (BrokenPipeError, OSError) as exc:
                raise ThetaDataError(
                    f"ThetaData provider worker communication failed: "
                    f"{type(exc).__name__}"
                ) from exc

            if not line:
                raise ThetaDataError("ThetaData provider worker returned no response")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ThetaDataError(
                    "ThetaData provider worker returned invalid protocol JSON"
                ) from exc

            if (
                not isinstance(response, dict)
                or response.get("id") != request_id
                or response.get("ok") is not True
            ):
                error_type = (
                    str(response.get("error_type"))
                    if isinstance(response, dict)
                    else "UNKNOWN"
                )
                import re
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", error_type):
                    error_type = "UnclassifiedProviderException"
                status = (
                    response.get("error_grpc_status")
                    if isinstance(response, dict) else None
                )
                allowed_status = {
                    "OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT",
                    "DEADLINE_EXCEEDED", "NOT_FOUND", "ALREADY_EXISTS",
                    "PERMISSION_DENIED", "RESOURCE_EXHAUSTED",
                    "FAILED_PRECONDITION", "ABORTED", "OUT_OF_RANGE",
                    "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE",
                    "DATA_LOSS", "UNAUTHENTICATED",
                }
                if status not in allowed_status:
                    status = None
                raise ThetaDataError(
                    f"ThetaData Python-library worker request failed: {error_type}",
                    provider_error_type=error_type,
                    provider_grpc_status=status,
                )
            return response

    def close(self) -> None:
        process = getattr(self, "process", None)
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        with _workers_lock:
            _workers.discard(self)


def close_all_workers() -> None:
    with _workers_lock:
        snapshot = list(_workers)
    for worker in snapshot:
        worker.close()


atexit.register(close_all_workers)


def _worker() -> _Worker:
    cached = getattr(_thread_state, "worker", None)
    if cached is not None and cached.process.poll() is None:
        return cached
    worker = _Worker(provider_python_path())
    _thread_state.worker = worker
    return worker


def reset_thread_worker_for_tests() -> None:
    cached = getattr(_thread_state, "worker", None)
    if cached is not None:
        cached.close()
    if hasattr(_thread_state, "worker"):
        delattr(_thread_state, "worker")


def _call(method_name: str, **kwargs: Any) -> ThetaDataResponse:
    started = time.perf_counter()
    response = _worker().request(method_name, kwargs)
    rows_raw = response.get("rows")
    if not isinstance(rows_raw, list) or any(
        not isinstance(row, dict) for row in rows_raw
    ):
        raise ThetaDataError("ThetaData worker response rows malformed")
    rows = tuple(
        {str(key): value for key, value in row.items()}
        for row in rows_raw
    )
    explicit_no_data = response.get("explicit_no_data", False)
    if type(explicit_no_data) is not bool:
        raise ThetaDataError("ThetaData worker no-data evidence is not boolean")
    if explicit_no_data and rows:
        raise ThetaDataError("ThetaData worker claimed no data alongside rows")
    canonical = _canonical_bytes(rows)
    library_version = response.get("library_version")
    environment_fingerprint = response.get("environment_fingerprint")
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
        explicit_no_data=explicit_no_data,
        library_version=(
            None if library_version is None else str(library_version)
        ),
        provider_environment_fingerprint=(
            None
            if environment_fingerprint is None
            else str(environment_fingerprint)
        ),
    )


def _day_text(value: str) -> str:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return date.fromisoformat(text).isoformat()


def option_history_hourly_quote_surface(
    *,
    symbol: str,
    date_et: str,
    right: str = "both",
    max_dte: int = 45,
    strike_range: int = 2,
) -> ThetaDataResponse:
    """Bound one historical quote request to a single session and 1h interval.

    The source is diagnostic only. Hourly snapshots cannot prove a 09:35/10:00
    fill or a minute-sensitive stop/target. Exact source acceptance is separate.
    """
    if max_dte < 1 or max_dte > 75:
        raise ValueError("max_dte must be in [1, 75]")
    if strike_range < 0 or strike_range > 8:
        raise ValueError("strike_range must be in [0, 8]")
    if right not in {"call", "put", "both"}:
        raise ValueError("invalid option right")
    day = _day_text(date_et)
    return _call(
        "option_history_quote",
        symbol=symbol,
        expiration="*",
        interval="1h",
        date=day,
        strike="*",
        right=right,
        start_time="09:30:00",
        end_time="16:00:00",
        max_dte=max_dte,
        strike_range=strike_range,
    )


def option_at_time_quote_surface(
    *,
    symbol: str,
    date_et: str,
    time_of_day_et: str,
    right: str = "call",
    max_dte: int = 75,
    strike_range: int | None = None,
) -> ThetaDataResponse:
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    day = _day_text(date_et)
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


def establish_option_quote_shared_authenticated_session() -> None:
    """Construct the single SDK auth session before any immutable query start.

    SDK authentication may contact ThetaData's authorization service, but
    this sends ZERO historical market-data requests. The established clients
    persist in the caller thread's isolated provider subprocess and are reused
    by all subsequent quote batches in that same process.
    """
    observed = _worker().request(
        "shared_authenticated_session_ready", {},
    )
    if (observed.get("shared_authenticated_session") is not True
            or observed.get("historical_quote_requests") != 0):
        raise ThetaDataError("shared quote authentication readiness failed")


def restart_option_quote_shared_authenticated_session_after_ambiguous_batch() -> None:
    """Discard a potentially broken worker, then authenticate a new session.

    Call ONLY after a complete historical batch response was not received.
    Caller must preserve the already STARTED query IDs as uncertain and never
    resend them. This creates no historical requests by itself.
    """
    reset_thread_worker_for_tests()
    establish_option_quote_shared_authenticated_session()


def option_at_time_quote_shared_session_batch(
    queries: list[dict[str, Any]],
) -> list[ThetaDataResponse | ThetaDataError]:
    """Up to four frozen independent quote scopes using ONE SDK login.

    No ThetaData SDK is imported into this interpreter. A single isolated
    worker process owns the authenticated base client and derives the others
    via ThetaData's documented existing_authorized_client parameter. The
    worker returns per-query original dataframe values without mixing them.
    Failure objects retain only type and standard gRPC classification.
    """
    if not isinstance(queries, list) or not 1 <= len(queries) <= 4:
        raise ValueError("shared session batch size must be 1..4")
    raw_queries: list[dict[str, Any]] = []
    for q in queries:
        if not isinstance(q, dict) or set(q) != {
            "symbol", "date_et", "time_of_day_et", "right",
            "max_dte", "strike_range",
        }:
            raise ValueError("shared session exact query shape changed")
        if (q["symbol"] != "SPY" or q["right"] != "both"
                or q["time_of_day_et"] != "10:00:00.000"
                or q["max_dte"] != 45 or q["strike_range"] != 2):
            raise ValueError("shared session frozen SPY query drift")
        day = _day_text(q["date_et"])
        raw_queries.append({
            "symbol": "SPY", "start_date": day, "end_date": day,
            "time_of_day": "10:00:00.000", "expiration": "*",
            "strike": "*", "right": "both",
            "max_dte": 45, "strike_range": 2,
        })
    return _execute_shared_option_quote_batch(raw_queries, expected_count=len(queries))


def _execute_shared_option_quote_batch(
    raw_queries: list[dict[str, Any]], *, expected_count: int,
) -> list[ThetaDataResponse | ThetaDataError]:
    """Decode existing four-client SDK batch for any strictly validated query shape."""
    started = time.perf_counter()
    batch = _worker().request(
        "batch_option_at_time_quote_shared_session",
        {"queries": raw_queries},
    )
    results = batch.get("results")
    if (batch.get("shared_authenticated_session") is not True
            or not isinstance(results, list)
            or len(results) != expected_count):
        raise ThetaDataError("shared authenticated SDK result shape unqualified")
    elapsed = max(0.0, time.perf_counter() - started)
    completed: list[ThetaDataResponse | ThetaDataError] = []
    for item in results:
        if not isinstance(item, dict):
            # A trustworthy ordered batch response can contain one malformed
            # item. Do not discard three OTHER completed provider results or
            # mark them as ambiguous: preserve their original evidence.
            completed.append(ThetaDataError(
                "ThetaData shared-session item invalid",
                provider_error_type="MalformedProviderBatchItem",
                provider_error_stage="DATAFRAME_SERIALIZATION",
            ))
            continue
        if item.get("ok") is not True:
            label = item.get("error_type")
            status = item.get("error_grpc_status")
            import re
            if not isinstance(label, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]{0,99}", label
            ):
                label = "UnclassifiedProviderException"
            valid_status = {
                "OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT",
                "DEADLINE_EXCEEDED", "NOT_FOUND", "ALREADY_EXISTS",
                "PERMISSION_DENIED", "RESOURCE_EXHAUSTED",
                "FAILED_PRECONDITION", "ABORTED", "OUT_OF_RANGE",
                "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE",
                "DATA_LOSS", "UNAUTHENTICATED",
            }
            completed.append(ThetaDataError(
                "ThetaData shared-session quote failed: " + label,
                provider_error_type=label,
                provider_grpc_status=(
                    status if status in valid_status else None
                ),
                provider_error_stage=item.get("error_stage"),
            ))
            continue
        rows = item.get("rows")
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) for row in rows
        ):
            completed.append(ThetaDataError(
                "ThetaData shared-session result rows invalid",
                provider_error_type="MalformedProviderQuoteRows",
                provider_error_stage="DATAFRAME_SERIALIZATION",
            ))
            continue
        explicit = item.get("explicit_no_data", False)
        if type(explicit) is not bool or (explicit and rows):
            completed.append(ThetaDataError(
                "ThetaData shared-session no-data evidence inconsistent",
                provider_error_type="ContradictoryProviderNoData",
                provider_error_stage="DATAFRAME_SERIALIZATION",
            ))
            continue
        try:
            canonical = _canonical_bytes(rows)
        except (TypeError, ValueError, OverflowError) as exc:
            # Nonfinite provider option quotes occasionally arrive as NaN/
            # inf. They must never be promoted as valid evidence, but one
            # failed right cannot consume three otherwise completed rights.
            completed.append(ThetaDataError(
                "ThetaData shared-session quote cannot be serialized safely",
                provider_error_type="UnserializableProviderQuoteRows",
                provider_error_stage="DATAFRAME_SERIALIZATION",
            ))
            continue
        completed.append(ThetaDataResponse(
            http_status=200,
            rows=tuple(rows),
            headers={
                "atlas-provider-transport": TRANSPORT,
                "atlas-provider-method": "option_at_time_quote",
            },
            response_bytes=len(canonical),
            elapsed_seconds=elapsed,
            raw_body=canonical,
            explicit_no_data=explicit,
            library_version=item.get("library_version"),
            provider_environment_fingerprint=item.get(
                "environment_fingerprint"
            ),
        ))
    return completed



def validate_option_at_time_quote_exact_queries(
    queries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Pre-dispatch pure local exact SPY query validation, at most four IDs.

    Deliberately separate from the V24 frozen broad-chain batch surface.
    Each request specifies one date/expiration/strike/right at 10:00 ET.
    This MUST run BEFORE immutable STARTED receipts are written; invalid
    fractional-strike syntax must never consume an undispatched identity.
    """
    if not isinstance(queries, list) or not 1 <= len(queries) <= 4:
        raise ValueError("exact contract shared batch size must be 1..4")
    raw_queries: list[dict[str, Any]] = []
    import re
    from decimal import Decimal, InvalidOperation
    for q in queries:
        if not isinstance(q, dict) or set(q) != {
            "symbol", "date_et", "time_of_day_et", "expiration", "strike", "right",
        }:
            raise ValueError("exact contract shared query shape changed")
        if (q["symbol"] != "SPY" or q["right"] not in {"call", "put"}
                or q["time_of_day_et"] != "10:00:00.000"
                or type(q["strike"]) is not str
                or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", q["strike"]) is None):
            raise ValueError("exact contract SPY clock/right/strike drift")
        try:
            strike_value = Decimal(q["strike"])
        except InvalidOperation as exc:
            raise ValueError("exact contract strike invalid") from exc
        if not strike_value.is_finite() or strike_value <= 0:
            raise ValueError("exact contract strike nonpositive")
        session = _day_text(q["date_et"])
        expiry = _day_text(q["expiration"])
        if expiry < session:
            raise ValueError("exact option already expired")
        raw_queries.append({
            "symbol": "SPY", "start_date": session, "end_date": session,
            "expiration": expiry, "strike": q["strike"], "right": q["right"],
            "time_of_day": "10:00:00.000",
        })
    return raw_queries



def option_at_time_quote_exact_shared_session_batch(
    queries: list[dict[str, str]],
) -> list[ThetaDataResponse | ThetaDataError]:
    """One authenticated session, up to four exact SPY historical quote GETs.

    Validation is shared identically with the pre-STARTED source campaign
    preflight. It never silently changes V24 frozen broad query behavior.
    """
    raw_queries = validate_option_at_time_quote_exact_queries(queries)
    return _execute_shared_option_quote_batch(raw_queries, expected_count=len(queries))


def option_at_time_quote(
    *,
    symbol: str,
    expiration: str,
    strike: str,
    right: str,
    date_et: str,
    time_of_day_et: str,
) -> ThetaDataResponse:
    day = _day_text(date_et)
    return _call(
        "option_at_time_quote",
        symbol=symbol,
        start_date=day,
        end_date=day,
        time_of_day=time_of_day_et,
        expiration=_day_text(expiration),
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
    if max_dte < 1:
        raise ValueError("max_dte must be positive")
    if strike_range is not None and strike_range < 0:
        raise ValueError("strike_range cannot be negative")
    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "date": _day_text(date_et),
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
        "expiration": _day_text(expiration),
        "strike": "*",
        "right": right,
        "date": _day_text(date_et),
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
