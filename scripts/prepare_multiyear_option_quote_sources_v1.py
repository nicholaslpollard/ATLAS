from __future__ import annotations

"""One-command, zero-provider-source bridge to existing exact-OCC quote cache."""

import argparse
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    PLAN_REL, freeze_quote_demand, _write_new,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    MultiYearQuoteBridgeError, build_local_bridge, write_local_bridge,
)
from packages.data.research_storage import inspect_research_storage
from scripts.run_multiyear_demand_quote_cache_v1 import _last_complete


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Prepare 2021–2025 frozen stock/news/option source demand")
    p.add_argument("--rights", choices=("call", "put", "both"), default="both")
    p.add_argument("--as-of-utc", default=None, help="Optional aware planning cutoff")
    a = p.parse_args(argv)
    print("ATLAS MULTIYEAR STOCK/NEWS/OPTION SOURCE BRIDGE — OFFLINE", flush=True)
    print("  Reuses accepted signed full stock case denominator, original 2022 quotes, "
          "existing D: chain bodies; no market API call.", flush=True)
    try:
        at = datetime.fromisoformat(a.as_of_utc) if a.as_of_utc else datetime.now(UTC)
        if at.tzinfo is None:
            raise MultiYearQuoteBridgeError("planning cutoff must be timezone aware")
        settings = load_settings(ROOT, "development")
        selected = build_local_bridge(settings, right=a.rights)
        selection_path, action = write_local_bridge(settings, selected)
        print(f"  source selection: {action} / {selection_path}", flush=True)
        print(f"  original cases: {selected['original_case_denominator']}", flush=True)
        print(f"  selected original-case/rights: {selected['selected_case_right_memberships']}",
              flush=True)
        for k, v in selected["by_status"].items():
            print(f"  {k}: {v}", flush=True)
        if not selected["cases"]:
            print("  No option identities available; no quote demand can be planned.", flush=True)
            return 3
        frozen = freeze_quote_demand(
            selected["cases"], asof_utc=at, last_completed_session=_last_complete(at),
        )
        path = settings.resolved_path(f"{PLAN_REL}_{frozen['plan_fingerprint'][:16]}.json")
        if path.exists() or path.is_symlink():
            if _read_object(path) != frozen:
                raise MultiYearQuoteBridgeError("prior quote demand plan changed")
            plan_action = "REUSED_IDENTICAL_EXACT_QUOTE_DEMAND"
        else:
            _write_new(path, frozen)
            plan_action = "WRITTEN_IMMUTABLE_EXACT_QUOTE_DEMAND"
        print(f"  quote plan: {plan_action} / {path}", flush=True)
        print(f"  quote plan source membership count: {frozen['requested_case_denominator']}",
              flush=True)
        print(f"  exact physical quote histories: {frozen['unique_physical_quote_queries']}",
              flush=True)
        print(f"  quote demand dispositions: {dict(sorted(Counter(x['disposition'] for x in frozen['memberships']).items()))}",
              flush=True)
        print(f"  current rolling source floor: {frozen['rolling_five_year_floor']}",
              flush=True)
        disk = inspect_research_storage(settings)
        print(f"  D: free GiB: {disk.disk_free_gib:.3f}", flush=True)
        print("  NO paid GET, option fill, trade return, 2026 protected replay, "
              "or strategy promotion authority.", flush=True)
        print("  Quote plan is ready for the existing --plan offline cache census; "
              "paid quote acquisition remains separately authorized.", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"SOURCE BRIDGE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Do not acquire or substitute any unverified source.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
