from __future__ import annotations

"""V10 offline V9 at-time adapter and original retained SPY source replay.

No ThetaData client construction, provider/broker calls, acquisition,
V7/V8 reservations, raw re-persistence, quote promotion or simulation.
The --replay-retained-spy option verifies and rereads the already-retained
2025-06-09 rejected 10:00 source using its original saved receipt.
"""

import argparse
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    diagnose_at_time_response, match_retained_spy_canary_to_v9,
    validate_exact_request, HybridAtTimeSourceGateError,
)
from packages.data.hybrid_options_frozen_research_demand_v1 import (
    build_frozen_research_demand,
)
from packages.data.options_native_spy_standard_canary_v1 import canary_design
from packages.providers.thetadata.client import (
    ThetaDataResponse, _canonical_bytes,
)
from scripts.audit_options_native_spy_standard_one_quote_v1 import (
    RETAINED_REL, audit_saved_quote,
)


def replay_retained_spy(settings, v9_report: dict) -> dict:
    path = settings.resolved_path(RETAINED_REL)
    # Independent original V1 source-audit validates all three original
    # retained files, immutable receipt lineage, raw bytes and SHA first.
    prior = audit_saved_quote(path, write=False)
    if (prior["replay"] != "REPRODUCED"
            or prior["replay_reason"] != "OUT_OF_SCOPE_OPTION_EXPIRATION"
            or prior["rows"] != 264):
        raise HybridAtTimeSourceGateError(
            "PINNED_SPY_CANARY_PRIOR_REJECTION_NOT_REPRODUCED"
        )
    design = canary_design()
    anchor = design["selected_anchor"]
    matches = [
        row for row in v9_report["requests"]
        if row["origin"] == "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE"
        and row["date_et"] == "2025-06-09"
    ]
    if len(matches) != 1:
        raise HybridAtTimeSourceGateError("FROZEN_SPY_CANARY_NOT_UNIQUE")
    row = matches[0]
    identity = match_retained_spy_canary_to_v9(
        row, original_query_fp=anchor["query_fingerprint"],
    )
    receipt = json.loads(
        (path.parent / "raw" / "single_quote.receipt.json").read_bytes()
    )
    raw = (path.parent / "raw" / "single_quote.json").read_bytes()
    if (receipt["body_sha256"] != prior["original_sha256"]
            or hashlib.sha256(raw).hexdigest() != prior["original_sha256"]):
        raise HybridAtTimeSourceGateError("PINNED_CANARY_RAW_RECEIPT_DRIFT")
    rows = json.loads(raw)
    if _canonical_bytes(rows) != raw:
        raise HybridAtTimeSourceGateError("PINNED_CANARY_CANONICAL_BYTES_DRIFT")
    source = ThetaDataResponse(
        http_status=receipt["http_status"], rows=tuple(rows),
        headers={}, response_bytes=len(raw), raw_body=raw,
        elapsed_seconds=0.0,
        transport=receipt["provider_transport"],
        library_version=receipt["provider_library_version"],
        provider_environment_fingerprint=
            receipt["provider_environment_fingerprint"],
        evidence_encoding=receipt["evidence_encoding"],
        explicit_no_data=receipt["explicit_no_data"],
    )
    observed = diagnose_at_time_response(row, source)
    if (observed["status"] != "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION"
            or observed["full_original_row_count"] != 264
            or observed["outside_requested_dte_rows"] != 144):
        raise HybridAtTimeSourceGateError("PINNED_CANARY_DTE_EVIDENCE_CHANGED")
    return {
        **identity,
        "original_retained_sha256": observed["original_source_sha256"],
        "full_rows": observed["full_original_row_count"],
        "in_dte_rows": observed["within_requested_dte_rows"],
        "over_dte_rows": observed["outside_requested_dte_rows"],
        "diagnostic_fingerprint": observed["diagnostic_fingerprint"],
        "admission_status": observed["status"],
        "provider_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay-retained-spy", action="store_true",
        help="Re-read verified 2025 SPY source; never write or call SDK",
    )
    args = parser.parse_args(argv)
    print("ATLAS EXACT DECISION-CLOCK AT-TIME QUOTE GATE V10", flush=True)
    print(
        "  NO PROVIDER CLIENT OR CALLS, NO QUOTE PROMOTION, "
        "NO RESERVATIONS OR SIMULATOR", flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        report = build_frozen_research_demand()
        rows = report["requests"]
        if len(rows) != 411:
            raise HybridAtTimeSourceGateError("FROZEN_SPY_PILOT_COUNT_DRIFT")
        for selected in (rows[0], next(
            x for x in rows if x["date_et"] == "2025-06-09"
        )):
            kwargs = validate_exact_request(selected)
            print(
                f"  source={selected['date_et']} {kwargs['symbol']} "
                f"clock={kwargs['time_of_day_et']} right={kwargs['right']} "
                f"max_dte={kwargs['max_dte']} strike_range={kwargs['strike_range']} "
                "status=SDK_MAPPING_ONLY_NO_PROVIDER_AUTHORITY",
                flush=True,
            )
        print(
            "  SDK method=option_at_time_quote_surface "
            "max_dte_forwarding=UNPROVEN paid_authority=False",
            flush=True,
        )
        if args.replay_retained_spy:
            observed = replay_retained_spy(settings, report)
            print(
                f"  retained_spy={observed['full_rows']} rows "
                f"in_dte={observed['in_dte_rows']} "
                f"out_dte={observed['over_dte_rows']} "
                f"state={observed['admission_status']}",
                flush=True,
            )
            print(
                f"  original_sha256={observed['original_retained_sha256']} "
                f"diagnostic_fingerprint={observed['diagnostic_fingerprint']}",
                flush=True,
            )
        else:
            print("  retained_source_replay=NOT_REQUESTED", flush=True)
        print(
            "  COMPLETE: provider_requests=0 broker_requests=0 "
            "simulations_run=0 source_promoted=False "
            "paid_authority=False files_written=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no provider fallback or new attempts",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
