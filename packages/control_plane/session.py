from __future__ import annotations

import secrets
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Mapping


CONTROL_PLANE_SESSION_CONTRACT_VERSION = (
    "control-plane-session-v1-same-origin-double-submit-csrf"
)
CONTROL_PLANE_SESSION_COOKIE = "atlas_control_session"
CONTROL_PLANE_CSRF_HEADER = "X-ATLAS-CSRF"


@dataclass(frozen=True, slots=True)
class ControlPlaneWriteAuthorization:
    allowed: bool
    error_code: str | None = None


class ControlPlaneSessionGuard:
    """Ephemeral same-origin guard for state-changing localhost requests.

    The token exists only in process memory and rotates when ATLAS restarts. The browser
    receives it from a same-origin GET and also receives an HttpOnly SameSite=Strict
    cookie. Mutations must supply application/json, an exact same-origin Origin header,
    the cookie, and the matching custom header. No credential values are involved.
    """

    def __init__(self, *, token: str | None = None) -> None:
        value = token or secrets.token_urlsafe(32)
        if len(value) < 32:
            raise ValueError("control plane session token is too short")
        self._token = value

    @property
    def csrf_token(self) -> str:
        return self._token

    def cookie_header(self) -> str:
        return (
            f"{CONTROL_PLANE_SESSION_COOKIE}={self._token}; "
            "Path=/; HttpOnly; SameSite=Strict"
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "contract_version": CONTROL_PLANE_SESSION_CONTRACT_VERSION,
            "csrf_token": self._token,
            "header_name": CONTROL_PLANE_CSRF_HEADER,
            "same_origin_required": True,
            "application_json_required": True,
            "live_execution_promoted": False,
        }

    def authorize_write(
        self,
        headers: Mapping[str, str],
        *,
        expected_origin: str,
    ) -> ControlPlaneWriteAuthorization:
        content_type = str(headers.get("Content-Type", ""))
        if content_type.split(";", 1)[0].strip().lower() != "application/json":
            return ControlPlaneWriteAuthorization(False, "JSON_CONTENT_TYPE_REQUIRED")
        origin = str(headers.get("Origin", "")).rstrip("/")
        if not origin or origin != expected_origin.rstrip("/"):
            return ControlPlaneWriteAuthorization(False, "SAME_ORIGIN_REQUIRED")
        header_token = str(headers.get(CONTROL_PLANE_CSRF_HEADER, ""))
        if not header_token or not secrets.compare_digest(header_token, self._token):
            return ControlPlaneWriteAuthorization(False, "CSRF_HEADER_INVALID")
        cookie_header = str(headers.get("Cookie", ""))
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return ControlPlaneWriteAuthorization(False, "SESSION_COOKIE_INVALID")
        morsel = cookie.get(CONTROL_PLANE_SESSION_COOKIE)
        cookie_token = morsel.value if morsel is not None else ""
        if not cookie_token or not secrets.compare_digest(cookie_token, self._token):
            return ControlPlaneWriteAuthorization(False, "SESSION_COOKIE_INVALID")
        return ControlPlaneWriteAuthorization(True, None)
