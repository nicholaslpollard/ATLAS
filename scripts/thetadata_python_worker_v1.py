from __future__ import annotations

"""Standalone ThetaData Python-library worker for an isolated provider environment.

Protocol:
- one JSON request per stdin line
- one JSON response per stdout line
- provider/library logs may go to stderr but never stdout

This file intentionally imports no ATLAS package so it can run inside the dedicated
ThetaData virtual environment whose protobuf dependency is incompatible with the
core ATLAS/Webull environment.
"""

import argparse
import contextlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import importlib.metadata
import hashlib
import inspect
import json
import math
import os
import re
from pathlib import Path
import sys
from typing import Any


TARGET_LIBRARY_VERSION = "1.0.12"
PROVIDER_PACKAGES = (
    "thetadata",
    "python-dotenv",
    "protobuf",
    "grpcio",
    "httpx",
    "pandas",
    "polars",
    "zstandard",
)
API_KEY_ENV = "THETADATA_API_KEY"
CREDENTIALS_FILE_ENV = "THETADATA_CREDENTIALS_FILE"


# Only these already-implemented read-only operations are authorized.
# The per-method keyword set is also the local SDK compatibility contract:
# an SDK upgrade may never silently change the wire call surface.
ALLOWED_METHOD_ARGUMENTS = {
    "option_history_quote": frozenset((
        "symbol", "expiration", "interval", "date", "strike", "right",
        "start_time", "end_time", "max_dte", "strike_range",
    )),
    "option_at_time_quote": frozenset((
        "symbol", "start_date", "end_date", "time_of_day", "expiration",
        "strike", "right", "max_dte", "strike_range",
    )),
    "option_history_open_interest": frozenset((
        "symbol", "date", "expiration", "strike", "right", "max_dte",
        "strike_range",
    )),
    "option_history_binomial_greeks_first_order": frozenset((
        "symbol", "date", "expiration", "strike", "right",
        "start_time", "end_time", "interval", "annual_dividend",
        "rate_type", "version", "binomial_steps", "strike_range",
    )),
}


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in value.split("."):
        digits = ""
        for char in token:
            if char.isdigit():
                digits += char
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("provider dataframe contains non-finite float")
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _scalar(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    raise TypeError(f"unsupported provider scalar {type(value).__name__}")


def _records(frame: Any) -> list[dict[str, Any]]:
    try:
        values = frame.to_dict(orient="records")
    except TypeError:
        values = None
    if isinstance(values, list):
        return [
            {str(key): _scalar(value) for key, value in row.items()}
            for row in values
        ]
    if hasattr(frame, "to_dicts"):
        values = frame.to_dicts()
        if isinstance(values, list):
            return [
                {str(key): _scalar(value) for key, value in row.items()}
                for row in values
            ]
    raise TypeError("ThetaData returned an unsupported dataframe")


def _dotenv_key_status() -> str:
    """Classify root .env assignment without returning secret bytes or length.

    Diagnostic statuses do not prove the SDK authenticates or accepts the key.
    """
    path = Path.cwd() / ".env"
    if not path.is_file():
        return "DOTENV_FILE_MISSING"
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "DOTENV_UNREADABLE"

    assignments = []
    export_syntax = False
    bom_key = False
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        raw_key, raw_value = line.split("=", 1)
        key = raw_key.strip()
        if key.startswith("export ") and key[7:].strip() == API_KEY_ENV:
            export_syntax = True
            continue
        if key.lstrip("\ufeff") != API_KEY_ENV:
            continue
        if key != API_KEY_ENV:
            bom_key = True
        assignments.append(bool(raw_value.strip().strip('"').strip("'").strip()))
    if export_syntax:
        return "DOTENV_EXPORT_SYNTAX_UNSUPPORTED_BY_PREFLIGHT"
    if bom_key:
        return "DOTENV_KEY_UTF8_BOM_PREFIX"
    if not assignments:
        return "DOTENV_KEY_ASSIGNMENT_MISSING"
    if len(assignments) > 1:
        return "DOTENV_KEY_ASSIGNMENT_DUPLICATED"
    return "DOTENV_KEY_NONEMPTY" if assignments[0] else "DOTENV_KEY_EMPTY"


def _auth_source() -> tuple[str, bool]:
    if str(os.environ.get(API_KEY_ENV, "")).strip():
        return "THETADATA_API_KEY_ENV", True
    creds = str(os.environ.get(CREDENTIALS_FILE_ENV, "")).strip()
    if creds and Path(creds).is_file():
        return "THETADATA_CREDENTIALS_FILE_ENV", True
    if Path.cwd().joinpath("creds.txt").is_file():
        return "DEFAULT_CREDS_FILE", True
    if Path.cwd().joinpath(".env").is_file():
        try:
            for raw in Path.cwd().joinpath(".env").read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == API_KEY_ENV and value.strip().strip('"').strip("'"):
                    return "THETADATA_DOTENV_API_KEY", True
        except (OSError, UnicodeError):
            # Malformed/unreadable local .env must return a secret-free status,
            # not abort the package-only preflight with decoder exception text.
            pass
    return "NOT_OBSERVED_LOCALLY", False


def _provider_environment() -> tuple[dict[str, str | None], str]:
    packages: dict[str, str | None] = {}
    for name in PROVIDER_PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    raw = json.dumps(
        packages,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return packages, hashlib.sha256(raw).hexdigest()


def _library_version() -> str | None:
    try:
        return importlib.metadata.version("thetadata")
    except importlib.metadata.PackageNotFoundError:
        return None


_MODULE_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.][A-Za-z_][A-Za-z0-9_]*){0,7}")


def _safe_missing_module_name(exc: ModuleNotFoundError) -> str | None:
    """Expose only an identifier from ModuleNotFoundError.name, never exception text.

    Python import exception strings can include filesystem paths or arbitrary
    untrusted context. A bounded dotted module identifier is sufficient to
    diagnose a missing dependency while preserving secret-free preflight.
    """
    name = getattr(exc, "name", None)
    if not isinstance(name, str) or len(name) > 100:
        return None
    return name if _MODULE_NAME_PATTERN.fullmatch(name) else None


def inspect_sdk_method_contract() -> dict[str, Any]:
    """Inspect installed SDK class methods without constructing a client or requesting data.

    A callable with only **kwargs is not evidence that our specific query
    keywords are supported. Fail closed pending a targeted SDK review instead
    of spending requests to discover an accidental signature change.
    """
    result: dict[str, Any] = {
        "compatible": False,
        "status": "LIBRARY_NOT_INSTALLED",
        "method_statuses": {},
        "provider_requests": 0,
        "greeks_dollar_dividend_keyword_status": "SDK_NOT_INSPECTED",
    }
    if _library_version() is None:
        return result
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from thetadata import ThetaClient
    except ModuleNotFoundError as exc:
        result["status"] = "SDK_IMPORT_FAILED_ModuleNotFoundError"
        result["missing_module"] = _safe_missing_module_name(exc)
        return result
    except Exception as exc:
        result["status"] = "SDK_IMPORT_FAILED_" + type(exc).__name__
        return result

    statuses: dict[str, str] = {}
    for name, expected in ALLOWED_METHOD_ARGUMENTS.items():
        method = getattr(ThetaClient, name, None)
        if not callable(method):
            statuses[name] = "MISSING_METHOD"
            continue
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError):
            statuses[name] = "UNINSPECTABLE_SIGNATURE"
            continue
        explicit = {
            key for key, param in params.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        has_var_keyword = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in params.values()
        )
        if expected - explicit and not has_var_keyword:
            statuses[name] = "KEYWORDS_NOT_ACCEPTED"
        elif expected - explicit:
            # A dynamic **kwargs adapter can accept the Python call, but only
            # a future bounded provider qualifier proves endpoint semantics.
            statuses[name] = "DYNAMIC_KEYWORDS_ACCEPTED_UNVERIFIED"
        else:
            statuses[name] = "EXPLICIT_KEYWORDS_PRESENT"
    result["method_statuses"] = statuses
    greeks_method = getattr(ThetaClient, "option_history_binomial_greeks_first_order", None)
    if callable(greeks_method):
        try:
            greeks_params = inspect.signature(greeks_method).parameters
            explicit_amount = greeks_params.get("annual_dividend_amount")
            if explicit_amount is not None and explicit_amount.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                dollar_status = "EXPLICIT_KEYWORD_PRESENT"
            elif any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in greeks_params.values()
            ):
                dollar_status = "DYNAMIC_KEYWORD_ACCEPTED_SEMANTICS_UNVERIFIED"
            else:
                dollar_status = "KEYWORD_NOT_ACCEPTED"
        except (TypeError, ValueError):
            dollar_status = "SIGNATURE_UNINSPECTABLE"
    else:
        dollar_status = "METHOD_UNAVAILABLE"
    result["greeks_dollar_dividend_keyword_status"] = dollar_status
    result["compatible"] = all(
        state in {
            "EXPLICIT_KEYWORDS_PRESENT",
            "DYNAMIC_KEYWORDS_ACCEPTED_UNVERIFIED",
        }
        for state in statuses.values()
    ) and len(statuses) == len(ALLOWED_METHOD_ARGUMENTS)
    result["status"] = (
        "EXPECTED_METHOD_SIGNATURES_PRESENT"
        if result["compatible"] else "SDK_METHOD_CONTRACT_UNQUALIFIED"
    )
    return result


def _shared_session_sdk_signature_status() -> str:
    """Static pinned class constructor inspection; no SDK client construction."""
    if _library_version() != TARGET_LIBRARY_VERSION:
        return "SHARED_CLIENT_SDK_VERSION_UNQUALIFIED"
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from thetadata import ThetaClient
        sig = inspect.signature(ThetaClient)
    except Exception:
        return "SHARED_CLIENT_SIGNATURE_UNAVAILABLE"
    return ("SHARED_AUTH_CONSTRUCTOR_EXPLICIT"
            if "existing_authorized_client" in sig.parameters
            else "SHARED_AUTH_CONSTRUCTOR_NOT_EXPLICIT")


def preflight() -> dict[str, Any]:
    version = _library_version()
    auth_source, auth_present = _auth_source()
    environment_packages, environment_fingerprint = _provider_environment()
    sdk = inspect_sdk_method_contract()
    return {
        "ok": True,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_meets_3_12": sys.version_info[:2] >= (3, 12),
        "thetadata_installed": version is not None,
        "thetadata_version": version,
        "thetadata_tested_version": TARGET_LIBRARY_VERSION,
        "thetadata_version_supported": (
            version is not None
            and _version_tuple(version) >= (1, 0, 9)
            and _version_tuple(version) < (2,)
        ),
        "auth_source": auth_source,
        "auth_material_present": auth_present,
        "dotenv_key_status": _dotenv_key_status(),
        "environment_packages": environment_packages,
        "environment_fingerprint": environment_fingerprint,
        "shared_authenticated_client_status": _shared_session_sdk_signature_status(),
        "sdk_contract_compatible": sdk["compatible"],
        "sdk_contract_status": sdk["status"],
        "sdk_missing_module": sdk.get("missing_module"),
        "sdk_method_statuses": sdk["method_statuses"],
        "sdk_greeks_dollar_dividend_keyword_status": sdk[
            "greeks_dollar_dividend_keyword_status"
        ],
        "provider_requests": 0,
    }


def _decode_date(value: Any) -> date:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def _convert_kwargs(method: str, raw: dict[str, Any]) -> dict[str, Any]:
    kwargs = dict(raw)
    for name in ("date", "start_date", "end_date"):
        if name in kwargs and kwargs[name] is not None:
            kwargs[name] = _decode_date(kwargs[name])
    if "expiration" in kwargs and kwargs["expiration"] not in {None, "*"}:
        kwargs["expiration"] = _decode_date(kwargs["expiration"])
    return kwargs


class Runtime:
    def __init__(self) -> None:
        self.client = None
        self.version = None
        self.environment_fingerprint = None
        self.shared_clients = None

    def ensure(self):
        if self.client is not None:
            return self.client
        version = _library_version()
        if version is None:
            raise RuntimeError("THETADATA_LIBRARY_NOT_INSTALLED")
        if version != TARGET_LIBRARY_VERSION:
            raise RuntimeError("THETADATA_LIBRARY_UNPINNED")
        if inspect_sdk_method_contract()["compatible"] is not True:
            raise RuntimeError("THETADATA_SDK_METHOD_CONTRACT_UNQUALIFIED")
        if sys.version_info[:2] < (3, 12):
            raise RuntimeError("PYTHON_3_12_PLUS_REQUIRED")
        with contextlib.redirect_stdout(sys.stderr):
            from thetadata import ThetaClient
            self.client = ThetaClient(dataframe_type="pandas")
        self.version = version
        _, self.environment_fingerprint = _provider_environment()
        return self.client

    def request_shared_batch(self, queries: list[dict[str, Any]]) -> dict[str, Any]:
        """At most four quote GETs through one authenticated SDK session.

        Only a single base ThetaClient performs independent authentication.
        Derived clients must explicitly support existing_authorized_client;
        if the installed pinned library lacks that keyword, refuse BEFORE
        issuing any quote request. Each query result stays independent.
        """
        if (not isinstance(queries, list) or not 1 <= len(queries) <= 4):
            raise RuntimeError("THETADATA_SHARED_BATCH_SIZE_NOT_1_TO_4")
        for q in queries:
            if (not isinstance(q, dict)
                    or not q
                    or set(q) - ALLOWED_METHOD_ARGUMENTS["option_at_time_quote"]
                    or "symbol" not in q
                    or "start_date" not in q
                    or "end_date" not in q
                    or "time_of_day" not in q):
                raise RuntimeError("THETADATA_SHARED_BATCH_ARGUMENTS_INVALID")
        # All query identities are independently pre-receipted by the ATLAS
        # outer coordinator, not by this isolated SDK worker.
        if self.shared_clients is None:
            with contextlib.redirect_stdout(sys.stderr):
                from thetadata import ThetaClient
            try:
                signature = inspect.signature(ThetaClient)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    "THETADATA_SHARED_CLIENT_SIGNATURE_UNINSPECTABLE"
                ) from exc
            if "existing_authorized_client" not in signature.parameters:
                raise RuntimeError(
                    "THETADATA_PINNED_SDK_SHARED_AUTH_NOT_SUPPORTED"
                )
            base = self.ensure()
            with contextlib.redirect_stdout(sys.stderr):
                from thetadata import ThetaClient
                self.shared_clients = [base]
                # All derived clients use the base's existing authorization.
                for _ in range(3):
                    self.shared_clients.append(ThetaClient(
                        existing_authorized_client=base,
                        dataframe_type="pandas",
                    ))
        def execute(index_and_query):
            index, q = index_and_query
            try:
                client = self.shared_clients[index]
                func = getattr(client, "option_at_time_quote")
                with contextlib.redirect_stdout(sys.stderr):
                    frame = func(**_convert_kwargs("option_at_time_quote", q))
                return {
                    "ok": True,
                    "rows": _records(frame),
                    "explicit_no_data": False,
                    "library_version": self.version,
                    "environment_fingerprint": self.environment_fingerprint,
                }
            except Exception as exc:
                if type(exc).__name__ == "NoDataFoundError":
                    return {
                        "ok": True, "rows": [], "explicit_no_data": True,
                        "library_version": self.version,
                        "environment_fingerprint": self.environment_fingerprint,
                    }
                return {"ok": False, **_sanitized_provider_exception(exc)}
        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            responses = list(pool.map(execute, enumerate(queries)))
        return {
            "ok": True,
            "results": responses,
            "library_version": self.version,
            "environment_fingerprint": self.environment_fingerprint,
            "shared_authenticated_session": True,
        }

    def request(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        # The frozen downstream plan supplies annual dividend dollars in the
        # field named annual_dividend. Current Python SDK docs define that name
        # as a DECIMAL YIELD; they reserve annual_dividend_amount for USD/share.
        # Do not silently submit economically incorrect historical Greeks.
        # A future versioned request/plan with explicit units and SDK proof must
        # replace this guard. Quotes and OI remain unaffected.
        if method == "option_history_binomial_greeks_first_order":
            raise RuntimeError("THETADATA_GREEKS_DIVIDEND_UNITS_UNQUALIFIED")
        # Reject unsupported calls BEFORE SDK construction/authentication.
        if method not in ALLOWED_METHOD_ARGUMENTS:
            raise RuntimeError("THETADATA_METHOD_NOT_ALLOWED")
        if not isinstance(kwargs, dict) or (
            set(kwargs) - ALLOWED_METHOD_ARGUMENTS[method]
        ):
            raise RuntimeError("THETADATA_KEYWORDS_NOT_ALLOWED")
        client = self.ensure()
        func = getattr(client, method, None)
        if func is None or not callable(func):
            raise RuntimeError("THETADATA_METHOD_UNAVAILABLE")
        try:
            with contextlib.redirect_stdout(sys.stderr):
                frame = func(**_convert_kwargs(method, kwargs))
        except Exception as exc:
            if type(exc).__name__ == "NoDataFoundError":
                return {
                    "ok": True,
                    "method": method,
                    "library_version": self.version,
                    "environment_fingerprint": self.environment_fingerprint,
                    "rows": [],
                    "explicit_no_data": True,
                }
            raise
        return {
            "ok": True,
            "method": method,
            "library_version": self.version,
            "environment_fingerprint": self.environment_fingerprint,
            "rows": _records(frame),
            "explicit_no_data": False,
        }


_SAFE_GRPC_STATUS_NAMES = frozenset({
    "OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT", "DEADLINE_EXCEEDED",
    "NOT_FOUND", "ALREADY_EXISTS", "PERMISSION_DENIED",
    "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION", "ABORTED",
    "OUT_OF_RANGE", "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE",
    "DATA_LOSS", "UNAUTHENTICATED",
})


def _sanitized_provider_exception(exc: Exception) -> dict[str, Any]:
    """Only permit fixed-shape class identifiers and standard gRPC statuses.

    Never retain the SDK exception message, underlying URLs or credentials.
    This metadata only describes *future* failed attempts and is NOT proof
    whether a possibly dispatched provider query executed on the server.
    """
    name = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", name):
        name = "UnclassifiedProviderException"
    status = None
    code_method = getattr(exc, "code", None)
    if callable(code_method):
        try:
            code = code_method()
            candidate = getattr(code, "name", None)
            if candidate in _SAFE_GRPC_STATUS_NAMES:
                status = candidate
        except Exception:
            pass
    return {"error_type": name, "error_grpc_status": status}


def serve() -> int:
    runtime = Runtime()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        request_id = None
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("REQUEST_NOT_OBJECT")
            request_id = payload.get("id")
            method = str(payload["method"])
            kwargs = payload.get("kwargs")
            if not isinstance(kwargs, dict):
                raise ValueError("KWARGS_NOT_OBJECT")
            if method == "batch_option_at_time_quote_shared_session":
                if set(kwargs) != {"queries"}:
                    raise ValueError("SHARED_BATCH_KEYWORDS_INVALID")
                result = runtime.request_shared_batch(kwargs["queries"])
            else:
                result = runtime.request(method, kwargs)
            response = {"id": request_id, **result}
        except Exception as exc:
            response = {
                "id": request_id,
                "ok": False,
                **_sanitized_provider_exception(exc),
                # Deliberately do not return exception text; provider/auth exceptions
                # can contain sensitive request context.
            }
        # os.write uses the original protocol fd even when individual SDK
        # request threads redirect Python's process-global sys.stdout.
        raw_response = (
            json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        off = 0
        while off < len(raw_response):
            chunk = os.write(1, raw_response[off:])
            if chunk <= 0:
                raise RuntimeError("WORKER_PROTOCOL_WRITE_FAILED")
            off += chunk
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    if args.preflight:
        print(json.dumps(preflight(), sort_keys=True, separators=(",", ":")))
        return 0
    if args.serve:
        return serve()
    parser.error("choose --serve or --preflight")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
