from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.control_plane.phase18_policy import (  # noqa: E402
    PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED,
    PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT,
)
from packages.core.settings import load_settings  # noqa: E402
from scripts.validate_dependency_lock import validate_dependency_lock  # noqa: E402
from scripts.validate_secret_hygiene import validate_secret_hygiene  # noqa: E402


CONTRACT_VERSION = "atlas-doctor-v1-local-sanitized-zero-provider-calls"

_CREDENTIAL_GROUPS: dict[str, tuple[str, ...]] = {
    "massive_rest": ("MASSIVE_API_KEY",),
    "massive_flat_files": ("MASSIVE_S3_ACCESS_KEY_ID", "MASSIVE_S3_SECRET_ACCESS_KEY"),
    "webull_paper": ("WEBULL_PAPER_APP_KEY", "WEBULL_PAPER_APP_SECRET"),
    "webull_live": ("WEBULL_LIVE_APP_KEY", "WEBULL_LIVE_APP_SECRET"),
    "alpaca_paper": ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET"),
    "alpaca_live": ("ALPACA_LIVE_API_KEY", "ALPACA_LIVE_API_SECRET"),
}

_ARTIFACTS: dict[str, str] = {
    "live_market_state": "data/live/market_state/current.json",
    "phase11_candidates": "data/derived/candidates/phase11/v1",
    "phase14_ai_review": "data/derived/ai_review/phase14/v1/manifests",
    "phase15_outcomes": "data/derived/execution/phase15/v1/outcomes",
}


def _run_text(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip()


def _git_report() -> dict[str, object]:
    head = _run_text(["git", "rev-parse", "HEAD"])
    branch = _run_text(["git", "branch", "--show-current"])
    status = _run_text(["git", "status", "--porcelain"])
    available = head is not None and status is not None
    dirty_count = len(status.splitlines()) if status else 0
    return {
        "available": available,
        "head": head if head else "UNAVAILABLE",
        "branch": branch if branch else "DETACHED_OR_UNAVAILABLE",
        "worktree_clean": available and dirty_count == 0,
        "dirty_entry_count": dirty_count,
    }


def _python_requirement() -> tuple[str, bool]:
    try:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "UNREADABLE", False
    requirement = str(data.get("project", {}).get("requires-python", ""))
    match = re.search(r">=\s*(\d+)\.(\d+)", requirement)
    if match is None:
        return requirement or "UNSPECIFIED", False
    minimum = (int(match.group(1)), int(match.group(2)))
    return requirement, sys.version_info[:2] >= minimum


def _runtime_report() -> dict[str, object]:
    requirement, supported = _python_requirement()
    node_path = shutil.which("node")
    node_version = _run_text([node_path, "--version"]) if node_path else None
    return {
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "python_requirement": requirement,
        "python_supported": supported,
        "node_available": node_path is not None,
        "node_version": node_version or "UNAVAILABLE",
    }


def credential_presence(env: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for label, names in _CREDENTIAL_GROUPS.items():
        configured = all(bool(str(env.get(name, "")).strip()) for name in names)
        result[label] = "CONFIGURED" if configured else "MISSING"
    return result


def _configuration_report() -> dict[str, object]:
    try:
        settings = load_settings(ROOT)
    except Exception as exc:
        return {
            "valid": False,
            "error_type": type(exc).__name__,
        }
    return {
        "valid": True,
        "environment": str(settings.app.environment.value),
        "trading_mode": str(settings.app.trading_mode.value),
        "market_scope": str(settings.app.market_scope.value),
        "timezone": settings.app.timezone,
        "canonical_timezone": settings.app.canonical_timezone,
    }


def _artifact_report() -> dict[str, str]:
    return {
        label: "PRESENT" if (ROOT / relative).exists() else "MISSING"
        for label, relative in _ARTIFACTS.items()
    }


def build_report(env: Mapping[str, str] | None = None) -> dict[str, object]:
    dependency_lock = validate_dependency_lock()
    secret_hygiene = validate_secret_hygiene()
    runtime = _runtime_report()
    repository = _git_report()
    configuration = _configuration_report()
    # load_settings() above loads the normal local .env without exposing values.
    environment = dict(os.environ if env is None else env)
    credentials = credential_presence(environment)
    artifacts = _artifact_report()

    core_pass = bool(
        dependency_lock["pass"]
        and secret_hygiene["pass"]
        and runtime["python_supported"]
        and repository["available"]
        and configuration["valid"]
    )

    warnings: list[str] = []
    if repository["available"] and not repository["worktree_clean"]:
        warnings.append("WORKTREE_DIRTY")
    if not runtime["node_available"]:
        warnings.append("NODE_UNAVAILABLE")
    for label, state in credentials.items():
        if state == "MISSING":
            warnings.append(f"CREDENTIAL_PROFILE_MISSING:{label}")
    for label, state in artifacts.items():
        if state == "MISSING":
            warnings.append(f"LOCAL_ARTIFACT_MISSING:{label}")

    return {
        "contract_version": CONTRACT_VERSION,
        "overall": "PASS" if core_pass else "FAIL",
        "repository": repository,
        "runtime": runtime,
        "configuration": configuration,
        "credentials": credentials,
        "local_artifacts": artifacts,
        "checks": {
            "dependency_lock": "PASS" if dependency_lock["pass"] else "FAIL",
            "secret_hygiene": "PASS" if secret_hygiene["pass"] else "FAIL",
        },
        "safety": {
            "provider_calls_performed": 0,
            "provider_writes_performed": 0,
            "phase18_provider_mutation_default": (
                "ALLOWED" if PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT else "DENIED"
            ),
            "phase18_explicit_target_authorization_required": (
                PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED
            ),
            "live_execution_promotion": (
                "ALLOWED" if PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED else "DISABLED"
            ),
            "automatic_cross_broker_failover": (
                "ALLOWED"
                if PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED
                else "DISABLED"
            ),
        },
        "warnings": sorted(warnings),
    }


def _print_human(report: dict[str, object]) -> None:
    repository = report["repository"]
    runtime = report["runtime"]
    configuration = report["configuration"]
    credentials = report["credentials"]
    artifacts = report["local_artifacts"]
    safety = report["safety"]

    print("ATLAS local doctor")
    print(f"Overall: {report['overall']}")
    print(
        "Repository: "
        f"head={repository['head']} branch={repository['branch']} "
        f"clean={repository['worktree_clean']}"
    )
    print(
        "Runtime: "
        f"Python {runtime['python_version']} ({runtime['python_requirement']}) "
        f"Node {runtime['node_version']}"
    )
    if configuration["valid"]:
        print(
            "Configuration: PASS · "
            f"environment={configuration['environment']} "
            f"mode={configuration['trading_mode']} "
            f"timezone={configuration['timezone']}"
        )
    else:
        print(f"Configuration: FAIL · {configuration['error_type']}")
    print("Credential presence (values never displayed):")
    for label, state in credentials.items():
        print(f"  {label}: {state}")
    print("Local artifacts:")
    for label, state in artifacts.items():
        print(f"  {label}: {state}")
    print(
        "Safety: "
        f"provider calls={safety['provider_calls_performed']} "
        f"provider writes={safety['provider_writes_performed']} "
        f"Phase18 mutation default={safety['phase18_provider_mutation_default']} "
        f"live={safety['live_execution_promotion']} "
        f"auto-failover={safety['automatic_cross_broker_failover']}"
    )
    warnings = report["warnings"]
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sanitized local ATLAS environment/repository doctor. It performs no provider "
            "calls and cannot authorize broker mutation or live execution."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the sanitized report as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
