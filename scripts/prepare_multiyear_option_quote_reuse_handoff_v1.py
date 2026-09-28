from __future__ import annotations

"""One zero-provider command: accepted PIT selections -> immutable replay source map."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import run_demand_cache
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    QuoteReuseHandoffError, assemble_quote_reuse_handoff,
    persist_quote_reuse_handoff,
)

SELECTION = Path(
    "data/options/manifests/"
    "multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json"
)
PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(
        description="Immutable all-case source-to-replay handoff; zero provider requests"
    )
    args.add_argument("--selection", type=Path, default=SELECTION)
    args.add_argument("--plan", type=Path, default=PLAN)
    a = args.parse_args(argv)
    print("ATLAS MULTIYEAR OPTION QUOTE SOURCE REUSE HANDOFF — OFFLINE", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        selection = _read_object(a.selection)
        plan = _read_object(a.plan)
        census = run_demand_cache(settings, plan)
        handoff = assemble_quote_reuse_handoff(selection, plan, census)
        output, action = persist_quote_reuse_handoff(settings, handoff)
        print(f"  source selection: {a.selection}", flush=True)
        print(f"  original stock cases: {handoff['original_case_denominator']}", flush=True)
        print(f"  selected case/rights: {handoff['selected_case_right_memberships']}", flush=True)
        print(f"  original 2022 reused quote queries: {handoff['reused_original_2022_queries']}", flush=True)
        print(f"  other exact complete quote queries: {handoff['verified_demand_cache_queries']}", flush=True)
        print(f"  genuinely pending in currently indexed caches: {handoff['pending_unique_quote_queries']}", flush=True)
        for year, statuses in handoff["by_year"].items():
            print(f"  {year}: {statuses}", flush=True)
        print(f"  output: {action} / {output}", flush=True)
        print(f"  handoff fingerprint: {handoff['handoff_fingerprint']}", flush=True)
        print("  Provider GETs: 0. Original 2022 receipts are reused; no option fill, "
              "account P&L or protected 2026 authority.", flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"QUOTE SOURCE HANDOFF STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Do not acquire or substitute any unverified source.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
