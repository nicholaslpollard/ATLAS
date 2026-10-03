from __future__ import annotations

"""Zero-provider-read readiness checks for the ThetaData Python library."""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sys
from typing import Any

from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)
from packages.providers.thetadata.client import (
    MIN_API_KEY_LIBRARY,
    MIN_PYTHON,
    TARGET_LIBRARY_VERSION,
    _version_tuple,
    installed_library_version,
)

API_KEY_ENV = "THETADATA_API_KEY"
CREDENTIALS_FILE_ENV = "THETADATA_CREDENTIALS_FILE"


@dataclass(frozen=True, slots=True)
class ThetaDataPreflightResult:
    python_major: int
    python_minor: int
    python_meets_minimum: bool
    library_installed: bool
    library_version: str | None
    library_meets_minimum: bool
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
    dotenv_path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str, bool]:
    env = os.environ if environ is None else environ
    if str(env.get(API_KEY_ENV, "")).strip():
        return "THETADATA_API_KEY_ENV", True

    if dotenv_path is not None and _dotenv_has_api_key(dotenv_path):
        return "THETADATA_DOTENV_API_KEY", True

    explicit_creds = str(env.get(CREDENTIALS_FILE_ENV, "")).strip()
    if explicit_creds and _creds_file_present(Path(explicit_creds)):
        return "THETADATA_CREDENTIALS_FILE_ENV", True

    if _creds_file_present(Path.cwd() / "creds.txt"):
        return "DEFAULT_CREDS_FILE", True

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
    dotenv_path: Path | None = None,
    environ: dict[str, str] | None = None,
    python_version: tuple[int, int] | None = None,
    library_version: str | None = None,
) -> ThetaDataPreflightResult:
    version = sys.version_info[:2] if python_version is None else python_version
    python_ok = tuple(version) >= MIN_PYTHON
    installed = (
        installed_library_version()
        if library_version is None
        else library_version
    )
    library_installed = installed is not None
    library_ok = (
        library_installed
        and _version_tuple(str(installed)) >= MIN_API_KEY_LIBRARY
        and _version_tuple(str(installed)) < (2,)
    )

    auth_source, auth_present = inspect_auth_source(
        dotenv_path=dotenv_path,
        environ=environ,
    )
    source_valid, enrichment_valid, plans_linked = validate_plans(
        source_plan,
        enrichment_plan,
    )

    details = [
        f"python={version[0]}.{version[1]} minimum={MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        (
            f"thetadata={installed} tested={TARGET_LIBRARY_VERSION}"
            if installed is not None
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
        "Theta Terminal and Java are not required for the active Python-library path",
    ]

    ready = python_ok and library_ok and auth_present and plans_linked
    if not python_ok:
        next_action = "USE_PYTHON_3_12_PLUS"
    elif not library_installed:
        next_action = "INSTALL_THETADATA_PYTHON_LIBRARY"
    elif not library_ok:
        next_action = "UPGRADE_THETADATA_PYTHON_LIBRARY"
    elif not auth_present:
        next_action = "CONFIGURE_THETADATA_AUTH"
    elif not plans_linked:
        next_action = "REPAIR_ATLAS_PLAN_LINKAGE"
    else:
        next_action = "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"

    return ThetaDataPreflightResult(
        python_major=int(version[0]),
        python_minor=int(version[1]),
        python_meets_minimum=python_ok,
        library_installed=library_installed,
        library_version=installed,
        library_meets_minimum=library_ok,
        tested_library_version=TARGET_LIBRARY_VERSION,
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
