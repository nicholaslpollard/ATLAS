from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.retained_stock_review_v1 import build_retained_stock_review
from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ConfigurationError
from packages.core.settings import load_settings


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3%}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile accepted retained stock aggregates; no new simulation or market/provider reads.")
    parser.add_argument("--save-report", action="store_true", help="Save one new JSON review; original artifacts remain read-only.")
    parser.add_argument("--selected-only", action="store_true", help="Use the exact frozen selected summary and six verified aggregates; omit full DEVELOPMENT/test returns and do not read route_summary.")
    args = parser.parse_args(argv)
    started = time.monotonic()
    print("ATLAS RETAINED STOCK RESULTS REVIEW V1", flush=True)
    scope = "two frozen summary snapshots / six aggregates; selected results only" if args.selected_only else "two summaries / five small aggregates"
    print(f"  scope: {scope}; no source replay or provider requests", flush=True)
    try:
        settings = load_settings(PROJECT_ROOT, "development")
    except (ConfigurationError, ValueError) as exc:
        print(f"  BLOCKED: configuration could not be loaded ({type(exc).__name__})", flush=True)
        return 3
    try:
        report = build_retained_stock_review(settings, progress=lambda detail: print(f"  [{time.monotonic() - started:.1f}s] {detail}", flush=True), selected_only=args.selected_only)
        totals = report["totals"]
        print(f"  routes / families: {totals['policy_routes']} / {totals['economic_families']}")
        print(f"  selected comparable / records: {totals['selected_comparable']:,} / {totals['selected_records']:,}")
        print(f"  selected mean primary / stress: {_pct(totals['selected_mean_primary_net_return'])} / {_pct(totals['selected_mean_stress_net_return'])}")
        print(f"  folds positive / negative: {totals['positive_primary_folds']} / {totals['negative_primary_folds']} of {totals['active_folds']}")
        print("  route directions (policy order; all losses and zero selections retained):")
        for row in report["route_directions"]:
            selected = row["return_subsets"]["WALK_FORWARD_SELECTED_COMPARABLE"]
            test = row["return_subsets"]["WALK_FORWARD_TEST_COMPARABLE"]
            fold = row["fold_consistency"]
            means = "n/a" if selected is None else " / ".join(_pct(selected[key]) for key in ("mean_gross_return", "mean_primary_net_return", "mean_stress_net_return"))
            test_mean = _pct(test["mean_primary_net_return"]) if test else "n/a"
            print(f"    {row['policy_id']} {row['direction']} ({row['native_timeframe']}): n={row['selected_comparable']:,}; gross/primary/stress={means}; test primary={test_mean}; folds +{fold['positive_primary_folds']}/-{fold['negative_primary_folds']}; largest={_pct(fold['largest_fold_share'])}")
            path = row["five_session_path"]
            if path:
                print(f"      path5: MFE={_pct(path['mean_mfe_5'])}; adverse={_pct(path['mean_adverse_excursion_5'])}; giveback={_pct(path['mean_peak_giveback'])}; median capture={_pct(path['median_exit_capture_ratio'])}")
                print("      first-touch " + " | ".join(f"{touch['move_threshold']:.0%}: favorable-first={_pct(touch['favorable_before_adverse_rate'])}, adverse-first={_pct(touch['adverse_before_favorable_rate'])}, unordered={_pct(touch['same_session_collision_rate'])}" for touch in row["five_session_first_touch"]))
        print("  horizons: daily return/path 5 sessions; baseline daily MFE/MAE 20 sessions")
        print("  account and week/month/year returns: not computed; evidence remains descriptive DEVELOPMENT")
        if args.selected_only:
            print("  full DEVELOPMENT/test route returns: unavailable; route_summary remains excluded and its original acceptance hash is unchanged")
        if args.save_report:
            directory = settings.resolved_path("data/research/retained_stock_review_v1")
            stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
            target = directory / f"{stamp}_{uuid.uuid4().hex[:8]}.json"
            atomic_write_text(target, json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", fsync=True)
            print(f"  saved report: {target}")
        print(f"  COMPLETE: {report['status']}; report fingerprint: {report['report_fingerprint']}")
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Retain existing evidence; resolve the named artifact/binding. No automatic rebuild or fallback was attempted.")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
