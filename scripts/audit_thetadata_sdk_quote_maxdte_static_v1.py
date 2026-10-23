from __future__ import annotations

"""Offline inspect pinned ThetaData option_at_time_quote implementation.

Default parent process runs one isolated provider-venv Python subprocess with
sanitized environment. Child imports the SDK CLASS only (no ThetaClient
constructor, method invocation, network client, account entitlement or GET).
Outputs approved AST/provenance classifications only: NO source code, package
file locations, credential material, values, tracebacks or SDK stdout.
"""

import ast
from collections import Counter
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = "1.0.12"
CONTRACT = "atlas-thetadata-option-at-time-quote-installed-sdk-static-audit-v1"
EXPECTED_METHOD = "option_at_time_quote"
CHILD_TIMEOUT_SECONDS = 25
MAX_CHILD_STDOUT = 24 * 1024
SOURCE_TEXT_LIMIT = 512 * 1024

SAFE_FIELDS = frozenset({
    "contract", "status", "library_version", "method", "method_callable",
    "explicit_max_dte_parameter", "var_keyword_parameter",
    "source_available", "source_sha256", "source_line_count",
    "max_dte_name_references", "max_dte_keyword_forward_calls",
    "max_dte_dict_value_forwards", "dynamic_kwargs_call_sites",
    "static_forwarding_classification", "provider_requests", "client_instances",
})


class StaticSdkAuditError(ValueError):
    pass


def classify_method_source(method: Any) -> dict[str, Any]:
    """Pure static analysis. inspect.getsource does not call *method*."""
    if not callable(method):
        raise StaticSdkAuditError("INSTALLED_METHOD_NOT_CALLABLE")
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError) as exc:
        raise StaticSdkAuditError("INSTALLED_METHOD_SIGNATURE_UNINSPECTABLE") from exc
    named = signature.parameters.get("max_dte")
    explicit = named is not None and named.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    has_varkw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in signature.parameters.values()
    )
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError):
        source = None
    if source is None:
        return {
            "method_callable": True, "explicit_max_dte_parameter": explicit,
            "var_keyword_parameter": has_varkw, "source_available": False,
            "source_sha256": None, "source_line_count": 0,
            "max_dte_name_references": 0,
            "max_dte_keyword_forward_calls": 0,
            "max_dte_dict_value_forwards": 0,
            "dynamic_kwargs_call_sites": 0,
            "static_forwarding_classification": "SOURCE_UNAVAILABLE_SEMANTICS_UNKNOWN",
        }
    if len(source.encode("utf-8")) > SOURCE_TEXT_LIMIT:
        raise StaticSdkAuditError("INSTALLED_METHOD_SOURCE_OVERSIZE")
    try:
        tree = ast.parse(textwrap.dedent(source))
    except (SyntaxError, IndentationError):
        # Decorator/class indentation or generated wrappers may be unsuitable
        # for direct AST; report unavailable without assuming absent filtering.
        return {
            "method_callable": True, "explicit_max_dte_parameter": explicit,
            "var_keyword_parameter": has_varkw, "source_available": False,
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "source_line_count": len(source.splitlines()),
            "max_dte_name_references": 0,
            "max_dte_keyword_forward_calls": 0,
            "max_dte_dict_value_forwards": 0,
            "dynamic_kwargs_call_sites": 0,
            "static_forwarding_classification": "AST_UNAVAILABLE_SEMANTICS_UNKNOWN",
        }
    counts = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "max_dte":
            counts["name"] += 1
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg is None:
                    counts["dynamic_calls"] += 1
                elif kw.arg == "max_dte" and (
                    isinstance(kw.value, ast.Name) and kw.value.id == "max_dte"
                ):
                    counts["call_forward"] += 1
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant) and key.value == "max_dte"
                    and isinstance(value, ast.Name) and value.id == "max_dte"
                ):
                    counts["dict_forward"] += 1
    if counts["call_forward"] or counts["dict_forward"]:
        status = "DIRECT_STATIC_FORWARDING_CANDIDATE_NOT_WIRE_PROOF"
    elif counts["name"]:
        status = "REFERENCED_BUT_FORWARDING_NOT_PROVED"
    else:
        status = "PARAMETER_BODY_FORWARDING_NOT_OBSERVED"
    # Decorators, dynamic calls and downstream SDK methods are outside the
    # observed AST boundary. This must never become 'endpoint proven good'.
    return {
        "method_callable": True,
        "explicit_max_dte_parameter": explicit,
        "var_keyword_parameter": has_varkw,
        "source_available": True,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "source_line_count": len(source.splitlines()),
        "max_dte_name_references": counts["name"],
        "max_dte_keyword_forward_calls": counts["call_forward"],
        "max_dte_dict_value_forwards": counts["dict_forward"],
        "dynamic_kwargs_call_sites": counts["dynamic_calls"],
        "static_forwarding_classification": status,
    }


def inspect_isolated_sdk_class() -> dict[str, Any]:
    """Import SDK class without constructing ThetaClient or reading credentials."""
    try:
        version = importlib.metadata.version("thetadata")
    except importlib.metadata.PackageNotFoundError as exc:
        raise StaticSdkAuditError("PINNED_SDK_NOT_INSTALLED") from exc
    if version != TARGET:
        raise StaticSdkAuditError("PINNED_SDK_VERSION_MISMATCH")
    try:
        # Suppress provider import output completely, including accidental
        # diagnostics, to avoid secrets and prevent JSON protocol pollution.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            from thetadata import ThetaClient
    except Exception as exc:
        raise StaticSdkAuditError("SDK_CLASS_IMPORT_FAILED_" + type(exc).__name__) from None
    method = inspect.getattr_static(ThetaClient, EXPECTED_METHOD, None)
    inspected = classify_method_source(method)
    return {
        "contract": CONTRACT, "status": "OFFLINE_INSTALLED_SDK_STATIC_INSPECTION",
        "library_version": version, "method": EXPECTED_METHOD,
        **inspected,
        "provider_requests": 0, "client_instances": 0,
    }


def _isolated_child() -> int:
    try:
        result = inspect_isolated_sdk_class()
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Safe static error code only, never exception text or SDK tracebacks.
        label = (str(exc) if isinstance(exc, StaticSdkAuditError)
                 else type(exc).__name__)
        if label not in (
            "PINNED_SDK_NOT_INSTALLED", "PINNED_SDK_VERSION_MISMATCH",
            "INSTALLED_METHOD_NOT_CALLABLE",
            "INSTALLED_METHOD_SIGNATURE_UNINSPECTABLE",
            "INSTALLED_METHOD_SOURCE_OVERSIZE",
        ) and not label.startswith("SDK_CLASS_IMPORT_FAILED_"):
            label = "OTHER_SDK_INSPECTION_FAILURE"
        print(json.dumps({"contract": CONTRACT, "status": "BLOCKED", "error_code": label,
                          "provider_requests": 0, "client_instances": 0}))
        return 3


def inspect_provider_sdk_offline(*, python_path: Path, runner=subprocess.run) -> dict[str, Any]:
    if not python_path.is_file():
        raise StaticSdkAuditError("ISOLATED_PROVIDER_PYTHON_UNAVAILABLE")
    if python_path.is_symlink():
        raise StaticSdkAuditError("ISOLATED_PROVIDER_PYTHON_LINK_UNQUALIFIED")
    # The child neither needs nor inherits API-key, login or ATLAS connector
    # variables. Avoid creating the SDK client and do not read .env.
    sanitized = {
        k: v for k, v in os.environ.items()
        if not any(marker in k.upper() for marker in (
            "API_KEY", "THETADATA", "TOKEN", "SECRET", "PASSWORD", "AUTH",
        ))
    }
    sanitized["PYTHONNOUSERSITE"] = "1"
    sanitized["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="atlas_sdk_static_") as tmp:
        try:
            process = runner(
                [str(python_path), str(Path(__file__).resolve()), "--isolated-child"],
                cwd=tmp, env=sanitized, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                capture_output=False, text=True, timeout=CHILD_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise StaticSdkAuditError(
                "ISOLATED_STATIC_INSPECTION_SUBPROCESS_" + type(exc).__name__
            ) from None
    if len(process.stdout) > MAX_CHILD_STDOUT:
        raise StaticSdkAuditError("ISOLATED_STATIC_REPORT_SIZE_EXCEEDED")
    try:
        report = json.loads(process.stdout)
    except (ValueError, TypeError):
        raise StaticSdkAuditError("ISOLATED_STATIC_REPORT_NOT_JSON") from None
    if (not isinstance(report, dict) or report.get("contract") != CONTRACT
            or report.get("provider_requests") != 0
            or report.get("client_instances") != 0):
        raise StaticSdkAuditError("ISOLATED_STATIC_REPORT_CONTRACT_CHANGED")
    if process.returncode != 0 or report.get("status") != "OFFLINE_INSTALLED_SDK_STATIC_INSPECTION":
        raise StaticSdkAuditError("ISOLATED_SDK_SOURCE_INSPECTION_BLOCKED")
    if set(report) != SAFE_FIELDS or report.get("library_version") != TARGET or report.get("method") != EXPECTED_METHOD:
        raise StaticSdkAuditError("ISOLATED_STATIC_REPORT_FIELDS_CHANGED")
    if not isinstance(report.get("source_available"), bool):
        raise StaticSdkAuditError("ISOLATED_STATIC_SOURCE_AVAILABILITY_INVALID")
    sha = report.get("source_sha256")
    if sha is not None and (
        not isinstance(sha, str) or len(sha) != 64
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise StaticSdkAuditError("ISOLATED_SOURCE_SHA_INVALID")
    for field in (
        "source_line_count", "max_dte_name_references", "max_dte_keyword_forward_calls",
        "max_dte_dict_value_forwards", "dynamic_kwargs_call_sites",
    ):
        if type(report[field]) is not int or report[field] < 0:
            raise StaticSdkAuditError("ISOLATED_STATIC_COUNTS_INVALID")
    return report


def main() -> int:
    print("ATLAS THETADATA 1.0.12 OPTION QUOTE MAX-DTE STATIC SDK AUDIT V1", flush=True)
    print("  ZERO SDK client construction, provider/broker requests or outcome access.", flush=True)
    try:
        from packages.core.settings import load_settings
        from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
        from packages.providers.thetadata.client import provider_python_path
        from packages.data.options_native_spy_standard_canary_v1 import canary_design
        from packages.core.atomic_io import atomic_write_text
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        design = canary_design()
        report = inspect_provider_sdk_offline(python_path=provider_python_path())
        report.update({
            "canary_source_design_fingerprint": design["design_fingerprint"],
            "observed_canary_max_dte": 45,
            "observed_full_rows": 264, "observed_in_dte_rows": 120,
            "observed_out_of_dte_rows": 144,
            "provider_sdk_or_server_cause_proved": False,
            "source_accepted": False, "further_paid_reads_authorized": False,
            "protected_outcomes_read": 0,
        })
        report["fingerprint"] = _fingerprint(report)
        target_dir = settings.resolved_path(
            "data/options/provider_qualification/options_native_spy_1000_v1"
        )
        output = target_dir / (
            "installed_sdk_max_dte_static_v1_" + report["fingerprint"][:16] + ".json"
        )
        payload = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if output.is_symlink() or (
            output.exists() and output.read_text(encoding="utf-8") != payload
        ):
            raise StaticSdkAuditError("STATIC_SDK_REPORT_CONFLICT")
        if not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(output, payload, fsync=True)
        print(f"  sdk_version={report['library_version']} method={report['method']}"
              f" explicit_max_dte={report['explicit_max_dte_parameter']}", flush=True)
        print(f"  source_available={report['source_available']}"
              f" source_sha256={report['source_sha256']}", flush=True)
        print(f"  max_dte_refs={report['max_dte_name_references']}"
              f" direct_keyword_forwards={report['max_dte_keyword_forward_calls']}"
              f" direct_dict_forwards={report['max_dte_dict_value_forwards']}"
              f" dynamic_kwargs_sites={report['dynamic_kwargs_call_sites']}", flush=True)
        print(f"  static_classification={report['static_forwarding_classification']}", flush=True)
        print("  cause_of_264_row_response=UNRESOLVED; SDK import alone is not wire evidence.",flush=True)
        print(f"  retained_report={output}", flush=True)
        print("  COMPLETE status=SDK_STATIC_ONLY provider_requests=0 source_accepted=False",flush=True)
        return 0
    except Exception as exc:
        print(f"  STOP class={type(exc).__name__} "
              "provider_requests=0; no fallback to live quotes", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(_isolated_child() if "--isolated-child" in sys.argv else main())
