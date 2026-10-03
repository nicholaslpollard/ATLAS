from __future__ import annotations

"""Zero-market-data ThetaData Terminal readiness checks.

The preflight never calls a ThetaData HTTP endpoint. It validates local prerequisites
only: Java 21+, expected loopback Terminal port reachability, optional local
authentication-source presence, and immutable ATLAS plan linkage.

A running Terminal can have been authenticated by a command-line API-key argument.
ATLAS intentionally does not inspect process command lines because that could expose a
secret. Therefore a reachable Terminal is reported as runtime-authenticated/unknown
without attempting to discover the credential source.
"""

from dataclasses import dataclass, asdict
import os
from pathlib import Path
import re
import socket
import subprocess
from typing import Any, Callable

from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)

JAVA_MIN_MAJOR = 21
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 25503
API_KEY_ENV = "THETADATA_API_KEY"


class ThetaDataPreflightError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ThetaDataPreflightResult:
    java_found: bool
    java_major: int | None
    java_meets_minimum: bool
    terminal_host: str
    terminal_port: int
    terminal_reachable: bool
    auth_source: str
    auth_material_present: bool
    source_plan_valid: bool
    enrichment_plan_valid: bool
    plans_linked: bool
    provider_requests: int
    ready_for_bounded_source_qualification: bool
    next_action: str
    detail: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_VERSION_PATTERNS = (
    re.compile(r'version\s+"(?P<major>\d+)(?:\.|")', re.IGNORECASE),
    re.compile(r'openjdk\s+(?P<major>\d+)(?:\.|\s)', re.IGNORECASE),
)


def parse_java_major(text: str) -> int | None:
    for pattern in _VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group("major"))
    return None


def inspect_java(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, int | None, str]:
    try:
        completed = runner(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return False, None, f"java unavailable: {type(exc).__name__}"

    output = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    ).strip()
    major = parse_java_major(output)
    if major is None:
        return True, None, "java found but version could not be parsed"
    return True, major, f"java major={major}"


def inspect_terminal_socket(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout_seconds: float = 1.0,
    connector: Callable[..., socket.socket] = socket.create_connection,
) -> tuple[bool, str]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ThetaDataPreflightError("ThetaData preflight permits loopback host only")
    if not 1 <= int(port) <= 65535:
        raise ThetaDataPreflightError("ThetaData terminal port is invalid")
    try:
        sock = connector((host, int(port)), timeout=timeout_seconds)
    except OSError as exc:
        return False, f"terminal socket not reachable: {type(exc).__name__}"
    try:
        return True, "terminal loopback socket reachable"
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _dotenv_has_api_key(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != API_KEY_ENV:
                continue
            value = value.strip().strip('"').strip("'")
            return bool(value)
    except OSError:
        return False
    return False


def _creds_file_present(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return len(lines) >= 2 and bool(lines[0].strip()) and bool(lines[1].strip())


def inspect_auth_source(
    *,
    terminal_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str, bool]:
    env = os.environ if environ is None else environ
    if str(env.get(API_KEY_ENV, "")).strip():
        return "THETADATA_API_KEY_ENV", True

    if terminal_dir is not None:
        base = terminal_dir.expanduser().resolve()
        if _dotenv_has_api_key(base / ".env"):
            return "TERMINAL_DOTENV_API_KEY", True
        if _creds_file_present(base / "creds.txt"):
            return "TERMINAL_CREDS_FILE", True

    return "NOT_OBSERVED_LOCALLY", False


def validate_plans(
    source_plan: dict[str, Any],
    enrichment_plan: dict[str, Any],
) -> tuple[bool, bool, bool]:
    source_valid = False
    enrichment_valid = False
    try:
        _check_signature(source_plan, "plan_fingerprint")
        source_valid = source_plan.get("contract") == SOURCE_PLAN_CONTRACT
    except Exception:
        source_valid = False
    try:
        _check_signature(enrichment_plan, "enrichment_plan_fingerprint")
        enrichment_valid = (
            enrichment_plan.get("contract") == ENRICHMENT_PLAN_CONTRACT
        )
    except Exception:
        enrichment_valid = False

    linked = (
        source_valid
        and enrichment_valid
        and enrichment_plan.get("source_plan_fingerprint")
            == source_plan.get("plan_fingerprint")
        and enrichment_plan.get("decision_spot_fingerprint")
            == source_plan.get("decision_spot_fingerprint")
    )
    return source_valid, enrichment_valid, linked


def run_thetadata_preflight_v1(
    *,
    source_plan: dict[str, Any],
    enrichment_plan: dict[str, Any],
    terminal_dir: Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    java_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    socket_connector: Callable[..., socket.socket] = socket.create_connection,
    environ: dict[str, str] | None = None,
) -> ThetaDataPreflightResult:
    details: list[str] = []
    java_found, java_major, java_detail = inspect_java(java_runner)
    details.append(java_detail)
    java_ok = java_found and java_major is not None and java_major >= JAVA_MIN_MAJOR

    terminal_reachable, terminal_detail = inspect_terminal_socket(
        host=host,
        port=port,
        connector=socket_connector,
    )
    details.append(terminal_detail)

    auth_source, auth_present = inspect_auth_source(
        terminal_dir=terminal_dir,
        environ=environ,
    )
    if terminal_reachable and not auth_present:
        details.append(
            "running Terminal may have command-line authentication; process arguments "
            "are intentionally not inspected"
        )
    elif auth_present:
        details.append(f"authentication material observed via {auth_source}")
    else:
        details.append("no local authentication source observed")

    source_valid, enrichment_valid, plans_linked = validate_plans(
        source_plan,
        enrichment_plan,
    )
    details.append(
        "ATLAS plan linkage valid"
        if plans_linked
        else "ATLAS source/enrichment plan linkage invalid"
    )

    ready = java_ok and terminal_reachable and plans_linked
    if ready:
        next_action = "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"
    elif not java_ok:
        next_action = "INSTALL_OR_UPGRADE_JAVA_21_PLUS"
    elif not terminal_reachable:
        next_action = (
            "START_THETA_TERMINAL"
            if auth_present
            else "CONFIGURE_AUTH_AND_START_THETA_TERMINAL"
        )
    else:
        next_action = "REPAIR_ATLAS_PLAN_LINKAGE"

    return ThetaDataPreflightResult(
        java_found=java_found,
        java_major=java_major,
        java_meets_minimum=java_ok,
        terminal_host=host,
        terminal_port=int(port),
        terminal_reachable=terminal_reachable,
        auth_source=auth_source,
        auth_material_present=auth_present,
        source_plan_valid=source_valid,
        enrichment_plan_valid=enrichment_valid,
        plans_linked=plans_linked,
        provider_requests=0,
        ready_for_bounded_source_qualification=ready,
        next_action=next_action,
        detail=tuple(details),
    )
