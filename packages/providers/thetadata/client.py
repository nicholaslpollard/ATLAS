from __future__ import annotations

"""Read-only ThetaData adapter backed by an isolated Python-library worker.

ThetaData 1.0.12 requires protobuf>=6.32.1 while the accepted ATLAS Webull SDK
requires protobuf<6 on Python>=3.12. To avoid destabilizing broker/runtime code,
ThetaData runs in a dedicated provider virtual environment and ATLAS communicates
with a persistent worker process over line-delimited JSON on stdin/stdout.

No Theta Terminal or Java is involved.
"""

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
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


class ThetaDataError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


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
    evidence_encoding: str = EVIDENCE_ENCODING


_thread_state = threading.local()


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
                stderr=subprocess.PIPE,
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

    def request(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        if self.process.poll() is not None:
            raise ThetaDataError("ThetaData provider worker exited unexpectedly")
        request_id = uuid.uuid4().hex
        payload = {
            "id": request_id,
            "method": method,
            "kwargs": kwargs,
        }
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        try:
            self.process.stdin.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
            )
            self.process.stdin.flush()
            line = self.process.stdout.readline()
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
            raise ThetaDataError(
                f"ThetaData Python-library worker request failed: {error_type}"
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
    canonical = _canonical_bytes(rows)
    library_version = response.get("library_version")
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
        library_version=(
            None if library_version is None else str(library_version)
        ),
    )


def _day_text(value: str) -> str:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return date.fromisoformat(text).isoformat()


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
