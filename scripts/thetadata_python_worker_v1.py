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
from datetime import date, datetime
import importlib.metadata
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


TARGET_LIBRARY_VERSION = "1.0.12"
PROVIDER_PACKAGES = (
    "thetadata",
    "protobuf",
    "grpcio",
    "httpx",
    "pandas",
    "polars",
    "zstandard",
)
API_KEY_ENV = "THETADATA_API_KEY"
CREDENTIALS_FILE_ENV = "THETADATA_CREDENTIALS_FILE"


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
        except OSError:
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


def preflight() -> dict[str, Any]:
    version = _library_version()
    auth_source, auth_present = _auth_source()
    environment_packages, environment_fingerprint = _provider_environment()
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
        "environment_packages": environment_packages,
        "environment_fingerprint": environment_fingerprint,
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

    def ensure(self):
        if self.client is not None:
            return self.client
        version = _library_version()
        if version is None:
            raise RuntimeError("THETADATA_LIBRARY_NOT_INSTALLED")
        if sys.version_info[:2] < (3, 12):
            raise RuntimeError("PYTHON_3_12_PLUS_REQUIRED")
        with contextlib.redirect_stdout(sys.stderr):
            from thetadata import ThetaClient
            self.client = ThetaClient(dataframe_type="pandas")
        self.version = version
        _, self.environment_fingerprint = _provider_environment()
        return self.client

    def request(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
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
            result = runtime.request(method, kwargs)
            response = {"id": request_id, **result}
        except Exception as exc:
            response = {
                "id": request_id,
                "ok": False,
                "error_type": type(exc).__name__,
                # Deliberately do not return exception text; provider/auth exceptions
                # can contain sensitive request context.
            }
        sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
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
