from __future__ import annotations

"""Zero-provider-read readiness checks for the isolated ThetaData Python worker."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)
from packages.providers.thetadata.client import (
    TARGET_LIBRARY_VERSION,
    WORKER_SCRIPT,
    provider_python_path,
)


@dataclass(frozen=True, slots=True)
class ThetaDataPreflightResult:
    provider_python: str
    provider_python_present: bool
    provider_python_version: str | None
    provider_python_meets_3_12: bool
    library_installed: bool
    library_version: str | None
    library_version_matches_tested: bool
    tested_library_version: str
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


def inspect_provider_environment(
    python_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not python_path.is_file():
        return {
            "provider_python_present": False,
            "python_version": None,
            "python_meets_3_12": False,
            "thetadata_installed": False,
            "thetadata_version": None,
            "thetadata_version_supported": False,
            "auth_source": "NOT_OBSERVED_LOCALLY",
            "auth_material_present": False,
            "provider_requests": 0,
        }
    try:
        completed = runner(
            [str(python_path), str(WORKER_SCRIPT), "--preflight"],
            cwd=str(WORKER_SCRIPT.parents[1]),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "provider_python_present": True,
            "python_version": None,
            "python_meets_3_12": False,
            "thetadata_installed": False,
            "thetadata_version": None,
            "thetadata_version_supported": False,
            "auth_source": "PREFLIGHT_EXECUTION_FAILED",
            "auth_material_present": False,
            "provider_requests": 0,
            "preflight_error_type": type(exc).__name__,
        }
    if completed.returncode != 0:
        return {
            "provider_python_present": True,
            "python_version": None,
            "python_meets_3_12": False,
            "thetadata_installed": False,
            "thetadata_version": None,
            "thetadata_version_supported": False,
            "auth_source": "PREFLIGHT_NONZERO_EXIT",
            "auth_material_present": False,
            "provider_requests": 0,
        }
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return {
            "provider_python_present": True,
            "python_version": None,
            "python_meets_3_12": False,
            "thetadata_installed": False,
            "thetadata_version": None,
            "thetadata_version_supported": False,
            "auth_source": "PREFLIGHT_INVALID_PROTOCOL",
            "auth_material_present": False,
            "provider_requests": 0,
        }
    return {
        "provider_python_present": True,
        "python_version": payload.get("python_version"),
        "python_meets_3_12": payload.get("python_meets_3_12") is True,
        "thetadata_installed": payload.get("thetadata_installed") is True,
        "thetadata_version": payload.get("thetadata_version"),
        "thetadata_version_supported": payload.get("thetadata_version_supported") is True,
        "auth_source": str(payload.get("auth_source") or "NOT_OBSERVED_LOCALLY"),
        "auth_material_present": payload.get("auth_material_present") is True,
        "provider_requests": int(payload.get("provider_requests") or 0),
    }


def run_thetadata_preflight_v1(
    *,
    source_plan: dict[str, Any],
    enrichment_plan: dict[str, Any],
    provider_python: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ThetaDataPreflightResult:
    python_path = provider_python_path() if provider_python is None else provider_python
    environment = inspect_provider_environment(python_path, runner=runner)
    source_valid, enrichment_valid, plans_linked = validate_plans(
        source_plan,
        enrichment_plan,
    )

    present = environment["provider_python_present"] is True
    py_ok = environment["python_meets_3_12"] is True
    library_installed = environment["thetadata_installed"] is True
    library_version = environment["thetadata_version"]
    version_matches = library_version == TARGET_LIBRARY_VERSION
    auth_present = environment["auth_material_present"] is True
    auth_source = str(environment["auth_source"])

    details = [
        (
            f"provider_python={python_path}"
            if present
            else f"provider Python not found at {python_path}"
        ),
        (
            f"provider_python_version={environment['python_version']}"
            if environment["python_version"]
            else "provider Python version unavailable"
        ),
        (
            f"thetadata={library_version} tested={TARGET_LIBRARY_VERSION}"
            if library_installed
            else f"thetadata not installed; tested={TARGET_LIBRARY_VERSION}"
        ),
        (
            f"authentication material observed via {auth_source}"
            if auth_present
            else "no ThetaData authentication source observed"
        ),
        (
            "ATLAS plan linkage valid"
            if plans_linked
            else "ATLAS source/enrichment plan linkage invalid"
        ),
        (
            "ThetaData runs in an isolated provider environment because its "
            "protobuf>=6 requirement conflicts with the accepted Webull SDK protobuf<6"
        ),
        "Theta Terminal and Java are not required",
    ]

    ready = (
        present
        and py_ok
        and library_installed
        and version_matches
        and auth_present
        and plans_linked
        and environment["provider_requests"] == 0
    )
    if not present:
        next_action = "SETUP_ISOLATED_THETADATA_PROVIDER_ENVIRONMENT"
    elif not py_ok:
        next_action = "RECREATE_PROVIDER_ENV_WITH_PYTHON_3_12_PLUS"
    elif not library_installed or not version_matches:
        next_action = "INSTALL_PINNED_THETADATA_PROVIDER_DEPENDENCIES"
    elif not auth_present:
        next_action = "CONFIGURE_THETADATA_AUTH"
    elif not plans_linked:
        next_action = "REPAIR_ATLAS_PLAN_LINKAGE"
    else:
        next_action = "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"

    return ThetaDataPreflightResult(
        provider_python=str(python_path),
        provider_python_present=present,
        provider_python_version=(
            None
            if environment["python_version"] is None
            else str(environment["python_version"])
        ),
        provider_python_meets_3_12=py_ok,
        library_installed=library_installed,
        library_version=(
            None if library_version is None else str(library_version)
        ),
        library_version_matches_tested=version_matches,
        tested_library_version=TARGET_LIBRARY_VERSION,
        auth_source=auth_source,
        auth_material_present=auth_present,
        source_plan_valid=source_valid,
        enrichment_plan_valid=enrichment_valid,
        plans_linked=plans_linked,
        provider_requests=int(environment["provider_requests"]),
        ready_for_bounded_source_qualification=ready,
        next_action=next_action,
        detail=tuple(details),
    )
