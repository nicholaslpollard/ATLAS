from __future__ import annotations

"""Provider-free preview or exactly ONE explicitly authorized ThetaData 1h quote.

No retries, year fallback, Greeks, OI, fills, simulations, or broad campaign.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.thetadata_hourly_source_canary_v1 import (
    design, run_one_hourly_source_canary,
)
from packages.providers.thetadata.client import (
    TARGET_LIBRARY_VERSION, close_all_workers, provider_python_path,
)
from packages.providers.thetadata.preflight import inspect_provider_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize-one-hourly-quote", action="store_true")
    parser.add_argument("--confirm-thetadata-standard", action="store_true")
    parser.add_argument("--acknowledge-one-quote-method-call", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS THETADATA SPY 2025 ONE-HOURLY-SOURCE CANARY V1", flush=True)
    try:
        original = design()
        print("  anchor=SPY 2025-06-09 interval=1h both rights "
              "09:30-16:00 ET max_dte=45 strike_range=2", flush=True)
        print("  source_design=" + original["design_fingerprint"], flush=True)
        flags = (
            args.authorize_one_hourly_quote,
            args.confirm_thetadata_standard,
            args.acknowledge_one_quote_method_call,
        )
        if not all(flags):
            if any(flags):
                print("  BLOCKED_PARTIAL_HOURLY_AUTHORIZATION provider_requests=0", flush=True)
                return 2
            print("  COMPLETE status=ONE_HOURLY_ANCHOR_DESIGN_ZERO_REQUESTS "
                  "provider_requests=0", flush=True)
            return 0

        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        preflight = inspect_provider_environment(provider_python_path())
        if not (
            preflight.get("provider_python_present") is True
            and preflight.get("python_meets_3_12") is True
            and preflight.get("thetadata_installed") is True
            and preflight.get("thetadata_version") == TARGET_LIBRARY_VERSION
            and preflight.get("sdk_contract_compatible") is True
            and preflight.get("auth_material_present") is True
            and preflight.get("provider_requests") == 0
        ):
            print("  BLOCKED_ISOLATED_SDK_AUTH_PREFLIGHT provider_requests=0", flush=True)
            return 3
        print("  OPERATOR_AUTHORIZED_ONE_READ method_cap=1 retries=0", flush=True)
        report = run_one_hourly_source_canary(
            settings,
            authorize_one_hourly_quote=True,
            confirm_thetadata_standard=True,
            acknowledge_one_quote_method_call=True,
        )
        diagnostic = report.get("source_diagnostics") or {}
        print(
            f"  provider_result={report['provider_result']} "
            f"requests_attempted={report['requests_attempted']} "
            f"rows={diagnostic.get('rows', 'unknown')} "
            f"outside_dte={diagnostic.get('out_of_requested_dte_rows', 'unknown')}",
            flush=True,
        )
        if "source_bytes" in report:
            print(
                f"  source_bytes={report['source_bytes']} "
                f"gzip_bytes={report['gzip_9_size_bytes']}",
                flush=True,
            )
        print("  retained_report=" + report["report_path"], flush=True)
        print("  COMPLETE status=HOURLY_SOURCE_DIAGNOSTIC_NO_PROMOTION "
              "provider_methods=1 protected_outcomes_read=0", flush=True)
        return 0 if report["provider_result"] == "OBSERVED_HOURLY_ROWS_SOURCE_DIAGNOSTIC" else 4
    except Exception as exc:
        print("  STOP failure_type=" + type(exc).__name__
              + "; no retries or additional provider calls authorized.", flush=True)
        return 3
    finally:
        close_all_workers()


if __name__ == "__main__":
    raise SystemExit(main())
