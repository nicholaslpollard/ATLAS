from __future__ import annotations

"""Decode only frozen, receipt-verified OCC histories into observed source marks."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    build_observed_option_timeline, local_verified_quote_reader,
    persist_observed_option_timeline,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zero-GET original case/right later-source option quote timeline"
    )
    parser.add_argument("--selection", type=Path, default=SELECTION)
    parser.add_argument("--plan", type=Path, default=QUOTE_PLAN)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    args = parser.parse_args()
    print("ATLAS MULTIYEAR VERIFIED OPTION QUOTE OBSERVATIONS — OFFLINE", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        selection = _read_object(args.selection)
        plan = _read_object(args.plan)
        handoff = _read_object(args.handoff)
        report = build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=local_verified_quote_reader(settings, plan),
        )
        path, action = persist_observed_option_timeline(settings, report)
        print(f"  original stock cases: {report['original_case_denominator']}", flush=True)
        print(f"  selected case/rights: {report['selected_case_right_memberships']}", flush=True)
        print(f"  verified unique raw histories decoded once: {report['unique_verified_physical_histories_decoded']}", flush=True)
        for year, counts in report["by_year"].items():
            print(f"  {year}: {counts}", flush=True)
        print(f"  derived source: {action} / {path}", flush=True)
        print(f"  fingerprint: {report['timeline_fingerprint']}", flush=True)
        print("  NO paid GET, original 09:35 fill, matched-clock stock option trade, "
              "verified deliverable, option P&L or strategy promotion.", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"OBSERVED QUOTE SOURCE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Original receipts preserved. No paid fallback or alternate contract.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
