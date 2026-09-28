from __future__ import annotations

"""One zero-provider workstation pass: quote timeline, stock EOD needs, pilot overlap."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_bridge_v1 import NATIVE_REL
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    build_observed_option_timeline, local_verified_quote_reader,
    persist_observed_option_timeline,
)
from packages.data.multiyear_option_stock_eod_preflight_v1 import (
    build_native_eod_needs, preview_pilot_quote_overlap,
    persist_pilot_overlap, persist_source_needs,
)
from packages.data.multiyear_native_eod_close_source_v1 import (
    resolve_native_eod_closes, persist_native_eod_closes,
)

SELECTION = Path(
    "data/options/manifests/"
    "multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json"
)
QUOTE_PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)
HANDOFF = Path(
    "data/options/manifests/"
    "multiyear_option_quote_reuse_handoff_v1_46e4c27c3d203581.json"
)
EXPECTED_HANDOFF_FP = "46e4c27c3d203581ae92c2f0ff653c9c3e65b1fa07f093a195dca2ecd8aff8cd"
EXPECTED_SELECTION_PREFIX = "3fa478312734f9c2"
EXPECTED_PLAN_PREFIX = "dbe759955e48946b"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One offline option timeline, legacy reuse and stock close-source demand"
    )
    parser.add_argument("--selection", type=Path, default=SELECTION)
    parser.add_argument("--plan", type=Path, default=QUOTE_PLAN)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--native-workers", type=int, default=3,
                        help="Original native daily-unit verification (1..4 workers)")
    args = parser.parse_args()
    print("ATLAS MULTIYEAR OPTIONS + NATIVE STOCK EOD PREFLIGHT — ZERO PROVIDER GETs",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        for category in ("options", "research_evidence"):
            settings.assert_external_storage_binding(category)
        selection, plan, handoff = (
            _read_object(args.selection), _read_object(args.plan), _read_object(args.handoff)
        )
        native = _read_object(settings.resolved_path(NATIVE_REL))
        if (handoff.get("handoff_fingerprint") != EXPECTED_HANDOFF_FP
            or not str(selection.get("selection_fingerprint", "")).startswith(
                EXPECTED_SELECTION_PREFIX
            )
            or not str(plan.get("plan_fingerprint", "")).startswith(
                EXPECTED_PLAN_PREFIX
            )):
            raise ValueError("accepted original source fingerprints differ")
        print("  stage=ORIGINAL_2025_PILOT_OVERLAP_PREVIEW", flush=True)
        overlap = preview_pilot_quote_overlap(settings, plan, handoff)
        print(f"    pilot_status={overlap['status']}", flush=True)
        print(f"    pending_unique_exact_queries={overlap['pending_unique_exact_requests']}",
              flush=True)
        print(f"    pilot_full_cover={overlap['candidate_full_coverage_sources']}", flush=True)
        print(f"    pilot_partial_overlap={overlap['candidate_partial_overlap_sources']}",
              flush=True)
        print(f"    pilot_counts={overlap['by_status']}", flush=True)

        print("  stage=VERIFY_AND_DECODE_ORIGINAL_QUOTE_HISTORIES", flush=True)
        timeline = build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=local_verified_quote_reader(settings, plan),
        )
        print(f"    physical_verified_histories={timeline['unique_verified_physical_histories_decoded']}",
              flush=True)
        for year, counts in timeline["by_year"].items():
            print(f"    quote_{year}={counts}", flush=True)

        print("  stage=FREEZE_NATIVE_RAW_EOD_CLOSE_DEMAND", flush=True)
        stock_needs = build_native_eod_needs(native, selection, timeline)
        print(f"    original_stock_cases={stock_needs['original_case_denominator']}", flush=True)
        print(f"    complete_right_denominator={stock_needs['original_right_memberships']}",
              flush=True)
        print(f"    case_rights_with_two_later_option_quotes="
              f"{stock_needs['case_rights_with_two_later_option_quote_dates']}", flush=True)
        print(f"    unique_native_raw_daily_close_requests="
              f"{stock_needs['unique_native_raw_eod_close_requests']}", flush=True)
        for year, counts in stock_needs["by_year"].items():
            print(f"    stock_{year}={counts}", flush=True)

        print("  stage=WRITE_ONLY_IMMUTABLE_D_BOUND_DERIVED_EVIDENCE", flush=True)
        p1, s1 = persist_observed_option_timeline(settings, timeline)
        p2, s2 = persist_source_needs(settings, stock_needs)
        p3, s3 = persist_pilot_overlap(settings, overlap)
        print(f"    quote_timeline={s1} / {p1}", flush=True)
        print(f"    stock_close_source_demand={s2} / {p2}", flush=True)
        print(f"    original_2025_pilot_overlap={s3} / {p3}", flush=True)
        print(f"    option_timeline_fingerprint={timeline['timeline_fingerprint']}", flush=True)
        print(f"    native_stock_demand_fingerprint={stock_needs['demand_fingerprint']}",
              flush=True)
        print(f"    pilot_overlap_fingerprint={overlap.get('overlap_fingerprint')}", flush=True)
        print("  stage=TARGETED_ORIGINAL_C_NATIVE_RAW_DAILY_CLOSE_SOURCE", flush=True)
        closes = resolve_native_eod_closes(
            settings, native, stock_needs, workers=args.native_workers,
            progress=lambda row: print(
                "    " + " ".join(f"{k}={v}" for k,v in row.items()), flush=True
            ),
        )
        p4, s4 = persist_native_eod_closes(settings, closes)
        print(f"    original_native_units_verified={closes['unique_native_daily_units_verified']}", flush=True)
        print(f"    exact_native_daily_closes={closes['verified_exact_native_raw_closes']}", flush=True)
        print(f"    native_daily_bar_gaps={closes['exact_daily_bar_gaps']}", flush=True)
        print(f"    native_close_source={s4} / {p4}", flush=True)
        print(f"    native_close_source_fingerprint={closes['source_fingerprint']}", flush=True)
        print("  No paid GET, historical 09:35 fill, synchronized stock-option"
              " timestamp claim, unverified deliverable, account return or"
              " strategy promotion.", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"INTEGRATED OFFLINE PREFLIGHT STOPPED: {type(exc).__name__}: {exc}",
              flush=True)
        print("  Original raw bodies, receipts and intent remain unchanged. "
              "No paid fallback or blind retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
