from __future__ import annotations

"""V11 ONE at-time quote qualification; offline preview by default.

A new diagnostic provider request is NOT the 9,866-request download campaign.
No paid API is called unless --manifest, --candidate-plan, --query-id and
ALL three explicit single-use provider acknowledgment flags are supplied.
The first attempted call globally locks V11 against any automatic repeat.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    inspect_one_qualification, run_one_qualification,
    PINNED_MANIFEST_FINGERPRINT,
)

DEFAULT_MANIFEST = (
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = (
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(DEFAULT_MANIFEST))
    parser.add_argument("--candidate-plan", type=Path, default=Path(DEFAULT_CANDIDATE))
    parser.add_argument("--query-id", type=str, help="Exact full 64-hex selected 2021 anchor")
    parser.add_argument("--authorize-one-paid-qualification-call", action="store_true")
    parser.add_argument("--acknowledge-sdk-max-dte-unproven", action="store_true")
    parser.add_argument("--acknowledge-permanent-no-automatic-retry", action="store_true")
    args = parser.parse_args(argv)
    requested = (
        args.authorize_one_paid_qualification_call
        or args.acknowledge_sdk_max_dte_unproven
        or args.acknowledge_permanent_no_automatic_retry
    )
    if requested and not (
        args.authorize_one_paid_qualification_call
        and args.acknowledge_sdk_max_dte_unproven
        and args.acknowledge_permanent_no_automatic_retry
        and args.query_id
    ):
        parser.error(
            "paid qualification requires full --query-id and ALL THREE "
            "single-call acknowledgment flags"
        )
    print("ATLAS 09:35 EXACT SINGLE-CALL QUALIFICATION GATE V11", flush=True)
    print(
        f"  mode={'EXPLICIT_ONE_PAID_DIAGNOSTIC_CALL' if requested else 'OFFLINE_NO_API_PREVIEW'} "
        "bulk_download_authorized=False simulations=0",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        if requested:
            result = run_one_qualification(
                settings, args.manifest, args.candidate_plan,
                query_id=args.query_id,
                authorize_one_paid_diagnostic_call=True,
                acknowledge_max_dte_unproven=True,
                acknowledge_no_retry_after_ambiguity=True,
            )
            print(
                f"  query_id={result['source_request_id']} "
                f"status={result['status']} "
                f"diagnostic_state={result['diagnostic_state']}",
                flush=True,
            )
            print(
                "  provider_calls_maximum=1 automatic_retry=False "
                "simulator_ready=False campaign_authorized=False",
                flush=True,
            )
            return 0 if result["status"] in (
                "SOURCE_ARCHIVED_DIAGNOSTIC_ONLY",
                "SOURCE_ARCHIVED_QUARANTINED_DTE",
            ) else 4

        preview = inspect_one_qualification(
            settings, args.manifest, args.candidate_plan,
            query_id=args.query_id,
        )
        choice = preview["qualifying_anchor"]
        print(
            f"  frozen_manifest={preview['manifest_fingerprint']} "
            f"candidate_2021_anchors={len(preview['eligible_2021_anchors'])}",
            flush=True,
        )
        print(
            f"  suggested_source={choice['date_et']} {choice['symbol']} "
            f"clock={choice['clock']} right={choice['right']} "
            f"max_dte={choice['max_dte']} strike_range={choice['strike_range']} "
            f"query_id={preview['source_request_id']}",
            flush=True,
        )
        for anchor in preview["eligible_2021_anchors"]:
            print(
                f"  anchor={anchor['date_et']} {anchor['symbol']} "
                f"query_id={anchor['query_id']}",
                flush=True,
            )
        print(
            f"  status={preview['status']} "
            f"safe_additional_gib={preview['safe_additional_budget_bytes']/1024**3:.3f} "
            f"outstanding_hourly_reservation_bytes={preview['outstanding_hourly_reservation_bytes']}",
            flush=True,
        )
        print(
            "  COMPLETE: no receipt, archive or provider calls written "
            "provider_requests=0 paid_authority=False "
            "max_dte_semantics_unproven=True simulator_ready=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__ + " "
            "NO_API_FALLBACK_NO_RETRY_NO_SIMULATION",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
