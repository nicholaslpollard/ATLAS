from __future__ import annotations

"""V12 exact historical options source acquisition with NO authorization prompts.

Default: offline read-only AAL saved response audit plus source-queue preview.
--run: resume collecting frozen 9,866 exact at-time sources, sequentially,
without per-call authorization flags or typing approval phrases.

--max-calls N is OPTIONAL for bounded work sessions; omitted means attempt
every remaining frozen request, subject to disk/quota and provider failures.
A pre-dispatch immutable query marker prevents automatic duplication after
ambiguous timeouts, and independently saved successes are reused.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT,
)
from packages.data.hybrid_options_saved_aal_audit_v1 import (
    HybridAalAuditError, audit_saved_aal,
)
from packages.data.hybrid_options_unattended_campaign_v1 import (
    preview_campaign, run_campaign,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_SOURCE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--run", action="store_true",
        help="Run unattended source collection; never asks for approval input",
    )
    parser.add_argument(
        "--max-calls", type=int,
        help="Optional requests this run (default: all remaining; NO fixed campaign limit)",
    )
    args = parser.parse_args(argv)
    if args.max_calls is not None and (args.max_calls < 1 or not args.run):
        parser.error("--max-calls requires --run and a positive integer")
    print("ATLAS HYBRID EXACT AT-TIME OPTIONS SOURCE CAMPAIGN V12", flush=True)
    print(
        "  mode=" + ("UNATTENDED_RESUMABLE_PROVIDER_ACQUISITION" if args.run
                  else "OFFLINE_SOURCE_AUDIT_AND_PREVIEW")
        + " interactive_authorization_prompts=0", flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        saved = audit_saved_aal(settings, args.manifest, args.candidate_plan)
        print(
            "  retained_aal=" + saved["status"]
            + f" original_rows={saved['total_original_rows']}"
            + f" in_dte={saved['in_dte_rows']}"
            + f" over_dte={saved['over_dte_rows']}"
            + f" expirations={saved['distinct_expiration_count']}"
            + f" gzip_bytes={saved['compressed_bytes']}"
            + f" original_bytes={saved['raw_bytes']}",
            flush=True,
        )
        print(
            f"  original_source_sha256={saved['archived_full_raw_sha256']}"
            f" dte_buckets={saved['dte_buckets']}", flush=True,
        )
        preview = preview_campaign(settings, args.manifest, args.candidate_plan)
        print(
            f"  frozen_requests={preview['total_frozen_requests']}"
            f" already_attempted={preview['counts']['previously_attempted']}"
            f" unknown_delivery={preview['counts']['uncertain_attempts']}"
            f" skipped_existing={preview['counts']['external_existing']}"
            f" remaining={preview['counts']['not_attempted']}",
            flush=True,
        )
        nxt = preview["next_request"]
        if nxt is not None:
            print(
                f"  next={nxt['date_et']} {nxt['symbol']} {nxt['clock']}"
                f" right={nxt['right']} priority={nxt['priority']}"
                f" query_id={nxt['query_id']}", flush=True,
            )
        print(
            "  storage_headroom_gib="
            f"{preview['storage']['available_after_hourly_reservations']/1024**3:.3f}"
            f" storage_safe={preview['storage']['safe']}",
            flush=True,
        )
        if args.run:
            result = run_campaign(
                settings, args.manifest, args.candidate_plan,
                max_calls=args.max_calls,
            )
            print(
                f"  calls={result['provider_calls_this_run']}"
                f" archives={result['archives_written_this_run']}"
                f" out_dte_archives={result['out_of_dte_archives_this_run']}"
                f" invalid_archives={result['invalid_schema_archives_this_run']}"
                f" stopped={result['stop_reason']}"
                f" last_id={result['last_query_id']}",
                flush=True,
            )
            print(
                "  COMPLETE: original_sources_only=True "
                "simulator_ready=False historical_execution_not_authorized=True",
                flush=True,
            )
            return 0 if result["stop_reason"] in {
                "FULL_FROZEN_MANIFEST_SCANNED",
                "OPTIONAL_RUN_REQUEST_LIMIT_REACHED",
            } else 4
        print(
            "  COMPLETE: provider_requests=0 no_new_files=True "
            "no_promotions=True simulator_ready=False",
            flush=True,
        )
        return 0
    except HybridAalAuditError as exc:
        # Only locally declared fixed error codes are used by this exception
        # class. They are safe to display and reveal no raw quotes, paths,
        # credentials, provider messages or SDK tracebacks. Without a code,
        # actual archived-only failures are impossible to diagnose remotely.
        code = str(exc)
        if code not in {
            "AAL_ARCHIVE_FILE_NOT_SAFE",
            "AAL_ARCHIVE_GZIP_INVALID",
            "AAL_ARCHIVE_BOUNDARY_OR_TRAILING_BYTES",
            "AAL_NOT_EXACT_FROZEN_QUERY",
            "AAL_FROZEN_REQUEST_SHAPE_DRIFT",
            "AAL_V11_TERMINAL_SCOPE_CHANGED",
            "AAL_V11_ARCHIVE_RECEIPT_DRIFT",
            "AAL_ARCHIVE_PATH_IDENTITY_DRIFT",
            "AAL_COMPRESSED_HASH_MISMATCH",
            "AAL_ORIGINAL_SHA_OR_SIZE_CHANGED",
            "AAL_CANONICAL_JSON_INVALID",
            "AAL_ORIGINAL_CANONICAL_ROWS_CHANGED",
            "AAL_ARCHIVED_ROWS_FAIL_V10_IDENTITY_REPLAY",
            "AAL_ARCHIVED_DTE_OVERRUN_NOT_REPRODUCED",
        }:
            code = "AAL_AUDIT_UNKNOWN_SAFE_FAILURE"
        print(
            "  BLOCKED: HybridAalAuditError code=" + code
            + " provider_requests=0 source_modified=False",
            flush=True,
        )
        return 3
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " original_sources_never_promoted=True",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
