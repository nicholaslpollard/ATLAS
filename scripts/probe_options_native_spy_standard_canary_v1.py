from __future__ import annotations

"""One exactly scoped ThetaData Options Standard SPY quote canary.

Default: zero provider requests. Paid invocation: explicit three flags, a
local SDK/auth-material preflight, then exactly ONE 2025 CALL+PUT at-time
quote source method attempt; no retries, OI, Greeks, fills or outcomes.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_spy_standard_canary_v1 import (
    canary_design, run_single_canary,
)
from packages.providers.thetadata.client import (
    TARGET_LIBRARY_VERSION, provider_python_path, close_all_workers,
)
from packages.providers.thetadata.preflight import inspect_provider_environment


def _offline_ready() -> tuple[bool, str]:
    status = inspect_provider_environment(provider_python_path())
    good = (
        status.get("provider_python_present") is True
        and status.get("python_meets_3_12") is True
        and status.get("thetadata_installed") is True
        and status.get("thetadata_version") == TARGET_LIBRARY_VERSION
        and status.get("sdk_contract_compatible") is True
        and status.get("auth_material_present") is True
        and status.get("provider_requests") == 0
        and isinstance(status.get("environment_fingerprint"), str)
        and len(status["environment_fingerprint"]) == 64
    )
    return good, str(status.get("sdk_contract_status") or "NOT_INSPECTED")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--authorize-one-standard-quote", action="store_true")
    p.add_argument("--confirm-thetadata-standard", action="store_true")
    p.add_argument("--acknowledge-one-quote-method-call", action="store_true")
    args = p.parse_args(argv)
    print("ATLAS THETADATA STANDARD SPY 2025 ONE-QUOTE CANARY V1", flush=True)
    try:
        design = canary_design()
        anchor = design["selected_anchor"]
        print(f"  original_pilot_design={design['source_design_fingerprint']} "
              f"canary_design={design['design_fingerprint']}", flush=True)
        print(f"  fixed_anchor={anchor['reason']} session={anchor['params']['start_date']} "
              "clock=10:00 ET right=both requests_cap=1", flush=True)
        authorized = (
            args.authorize_one_standard_quote
            and args.confirm_thetadata_standard
            and args.acknowledge_one_quote_method_call
        )
        if not authorized:
            if any((args.authorize_one_standard_quote, args.confirm_thetadata_standard,
                    args.acknowledge_one_quote_method_call)):
                print("  BLOCKED_PARTIAL_ONE_QUOTE_AUTHORIZATION provider_requests=0", flush=True)
                return 2
            print("  COMPLETE status=ONE_ANCHOR_DESIGN_ZERO_READS provider_requests=0", flush=True)
            return 0
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        ready, sdk = _offline_ready()
        print(f"  offline_provider_preflight={'PASSED' if ready else 'BLOCKED'} "
              f"sdk_status={sdk} provider_requests=0", flush=True)
        if not ready:
            return 3
        print("  OPERATOR_AUTHORIZED_ONE_READ: no further calls or historical fallback.", flush=True)
        result = run_single_canary(
            settings, authorize_one_standard_quote=True,
            confirm_thetadata_standard=True,
            acknowledge_one_quote_method_call=True,
        )
        print(f"  provider_result={result['provider_result']} "
              f"requests_attempted={result['requests_attempted']}", flush=True)
        if "quote_diagnostics" in result:
            diag = result["quote_diagnostics"]
            print(f"  quote_rows={diag['row_count']} calls={diag['call_rows']} "
                  f"puts={diag['put_rows']} clock_qualified_pairs={diag['clock_qualified_common_pairs']}",
                  flush=True)
        print("  retained_report=" + result["report_path"], flush=True)
        print("  COMPLETE status=ONE_QUOTE_SOURCE_DIAGNOSTIC_NOT_ACCEPTED "
              "provider_quote_methods=1 protected_outcomes_read=0", flush=True)
        return 0 if result["provider_result"] == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC" else 4
    except Exception as exc:
        print(f"  STOP failure_type={type(exc).__name__}. "
              "No additional provider methods authorized.", flush=True)
        return 3
    finally:
        close_all_workers()


if __name__ == "__main__":
    raise SystemExit(main())
