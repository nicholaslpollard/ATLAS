from __future__ import annotations

"""V23 SPY exit-source acquisition in one shared ThetaData auth session.

Default previews and verifies existing frozen originals, zero provider calls.
--sdk-preflight additionally checks the PINNED installed SDK constructor
keyword without constructing any SDK client or contacting ThetaData.
--run makes paid requests only after passing that static SDK gate.
All preexisting V19/V20/V22 attempted query IDs are skipped unchanged.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_exit_shared_session_campaign_v1 import (
    run_shared_exit_campaign,
)
from packages.data.options_native_exit_source_campaign_v1 import (
    preview_exit_campaign,
)
from packages.providers.thetadata.client import (
    establish_option_quote_shared_authenticated_session,
    provider_python_path, WORKER_SCRIPT,
)
from scripts.run_options_native_spy_exit_source_campaign_v1 import (
    DEFAULT_MANIFEST, DEFAULT_CANDIDATE,
)


def _provider_shared_signature_preflight() -> dict:
    """One zero-provider subprocess static SDK check; no key values logged."""
    try:
        checked = subprocess.run(
            [str(provider_python_path()), str(WORKER_SCRIPT), "--preflight"],
            cwd=str(ROOT),
            capture_output=True, text=True, timeout=60,
            check=True,
        )
        if len(checked.stdout) > 16384:
            raise ValueError("SDK_PREFLIGHT_OVERSIZE")
        report = json.loads(checked.stdout)
    except Exception as exc:
        raise RuntimeError(
            "SHARED_AUTH_SDK_LOCAL_PREFLIGHT_FAILED_" + type(exc).__name__
        ) from None
    if (report.get("thetadata_version") != "1.0.12"
            or report.get("python_meets_3_12") is not True
            or report.get("auth_material_present") is not True
            or report.get("sdk_contract_compatible") is not True
            or report.get("shared_authenticated_client_status") !=
                "SHARED_AUTH_CONSTRUCTOR_EXPLICIT"):
        raise RuntimeError("SHARED_AUTH_PINNED_SDK_CONSTRUCTOR_NOT_QUALIFIED")
    return {
        "thetadata_version": report["thetadata_version"],
        "shared_authenticated_client_status":
            report["shared_authenticated_client_status"],
        "auth_material_present": True,
        "sdk_contract_compatible": True,
        "provider_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--sdk-preflight", action="store_true")
    parser.add_argument("--run", action="store_true",
                        help="Explicitly submit paid historical quote queries")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--progress-every", type=int, default=4)
    args = parser.parse_args(argv)
    if (args.max_calls is not None and (
        args.max_calls < 1 or not args.run
    )):
        parser.error("positive --max-calls requires --run")
    if args.progress_every < 1:
        parser.error("progress cadence must be positive")
    print("ATLAS V23 SPY EXIT SINGLE AUTHENTICATED SESSION")
    print(
        "  mode=" + ("PAID_SHARED_SESSION_FROZEN_EXIT_SOURCE_ONLY"
                     if args.run else "OFFLINE_FROZEN_EXIT_SOURCE_PREVIEW"),
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        before = preview_exit_campaign(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  remaining={before['remaining_unattempted']}"
            f" states={before['exit_source_states']}"
            f" source_fp={before['plan_fingerprint']}"
            f" shared_storage_safe={before['shared_storage_safe']}",
            flush=True,
        )
        if args.sdk_preflight or args.run:
            report = _provider_shared_signature_preflight()
            print(
                "  SDK_PREFLIGHT"
                f" version={report['thetadata_version']}"
                f" shared_auth={report['shared_authenticated_client_status']}"
                " provider_requests=0", flush=True,
            )
        if not args.run:
            print("  COMPLETE: provider_requests=0 no_source_changes=True")
            return 0
        if not before["shared_storage_safe"]:
            raise RuntimeError("STORAGE_HEADROOM_NOT_SAFE")
        # SDK auth/derived client creation is verified before even ONE
        # frozen query identity is labeled possibly-dispatched. This
        # contacts auth service only, not historical quote endpoint.
        establish_option_quote_shared_authenticated_session()
        print(
            "  SDK_SHARED_AUTH_READY clients=4 independent_logins=1"
            " historical_quote_requests=0", flush=True,
        )
        result = run_shared_exit_campaign(
            settings, args.manifest, args.candidate_plan,
            max_calls=args.max_calls,
            progress_every=args.progress_every,
            progress=lambda e: print(
                f"  PROGRESS: calls={e['calls']}"
                f" archives={e['archived']}"
                f" over_dte={e['over_dte']}"
                f" last_date={e['date_et']}"
                f" query_id={e['query_id']}"
                f" state={e['state']}"
                + (
                    f" provider_class={e['provider_failure_class']}"
                    f" grpc_status={e['provider_grpc_status']}"
                    f" provider_stage={e.get('provider_error_stage')}"
                    if e.get("provider_failure_class") or e.get("provider_grpc_status")
                    else ""
                ), flush=True,
            ),
        )
        print(
            f"  dispatched={result['provider_calls_this_run']}"
            f" completed={result['completed_provider_calls_this_run']}"
            f" archives={result['archives_this_run']}"
            f" out_dte={result['outside_dte_archives_this_run']}"
            f" invalid_archives={result['invalid_archives_this_run']}"
            f" provider_faults={result['provider_faults_this_run']}"
            f" isolated_value_errors={result['isolated_value_errors_this_run']}"
            f" hard_provider_faults={result['hard_provider_faults_this_run']}"
            f" full_storage_audits={result['full_storage_audits_this_run']}"
            f" stop={result['stop_reason']}", flush=True,
        )
        after = preview_exit_campaign(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  remaining={after['remaining_unattempted']}"
            f" final_states={after['exit_source_states']}",
            flush=True,
        )
        print(
            "  COMPLETE: source_only=True simulator_ready=False"
            " simulations_run=0 protected_outcomes_read=0", flush=True,
        )
        return 0 if result["stop_reason"] in {
            "ALL_NEW_EXIT_SCOPES_SCANNED", "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED",
        } else 4
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " source_promotion=False automatic_retry=False", flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
