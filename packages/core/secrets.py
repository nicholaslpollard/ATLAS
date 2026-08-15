from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .exceptions import SecretNotFoundError

_REDACTED = "***REDACTED***"
_SECRET_MARKERS = ("key", "secret", "token", "password", "credential", "authorization")


def get_secret(env_name: str, *, required: bool = True) -> str | None:
    """Read a secret from the process environment only.

    ATLAS intentionally does not support hard-coded fallback values for secrets.
    """
    value = os.getenv(env_name)
    if value is not None:
        value = value.strip()
    if not value:
        if required:
            raise SecretNotFoundError(f"Required secret environment variable is not set: {env_name}")
        return None
    return value


def redact_value(value: str | None) -> str | None:
    return _REDACTED if value else value


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively redacted copy suitable for logging."""
    out: dict[str, Any] = {}
    for key, value in values.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            out[str(key)] = _REDACTED if value is not None else None
        elif isinstance(value, Mapping):
            out[str(key)] = redact_mapping(value)
        else:
            out[str(key)] = value
    return out
