from __future__ import annotations

"""Offline audit of already saved selected CALL quote histories; never re-query providers."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_2025_quote_diagnostic_v1 import (
    build_offline_dossier, write_local_dossier,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="No-provider-read, immutable selected EOD quote diagnostic.")
    parser.add_argument("--write-local-dossier", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        result = build_offline_dossier(settings)
        action, path = write_local_dossier(settings, result, authorize=args.write_local_dossier)
        counts = result["aggregate"]
        print("ATLAS 2025 Selected CALL EOD Offline Diagnostic V1", flush=True)
        print(f"  original quote source run: {result['accepted_original_quote_run_fingerprint']}", flush=True)
        print(f"  original quote plan: {result['quote_plan_fingerprint']}", flush=True)
        print(f"  offline dossier: {action} / {path}", flush=True)
        print(
            f"  original receipts={result['source_receipts_reused']} "
            f"EOD rows={counts['eod_rows']} positive_volume={counts['positive_volume_rows']} "
            f"zero_volume={counts['zero_volume_rows']} NEW provider GETs=0",
            flush=True,
        )
        for row in result["per_contract"]:
            m = row["metrics"]
            print(
                f"  {row['ticker']:<5} rows={m['total_eod_source_rows']:>2} "
                f"positive={m['positive_volume_rows']:>2} zero={m['zero_volume_rows']:>2} "
                f"decision_day_EOD_future_at_0935={m['same_decision_day_eod_rows_unavailable_at_0935']} "
                f"first_later_positive={m['first_post_decision_positive_volume_source_session'] or 'NONE'} "
                f"two_sided_EOD_context={m['observed_two_sided_eod_quote_geometry_rows']:>2} "
                f"{m['observation_classification']}",
                flush=True,
            )
        print(f"  all-zero-volume series: {', '.join(counts['no_positive_volume_series'])}", flush=True)
        print(
            "  no positive-volume observation AFTER original decision session: "
            + (", ".join(counts["no_post_decision_positive_volume_series"]) or "NONE"),
            flush=True,
        )
        print(f"  EOD two-sided geometry rows: {counts['eod_two_sided_quote_geometry_rows']}", flush=True)
        print(f"  zero-volume rows with a positive last (not same-session trades): {counts['zero_volume_with_positive_last']}", flush=True)
        print(f"  dossier fingerprint: {result['dossier_fingerprint']}", flush=True)
        print(
            "  source observations only; no verified deliverable, intraday entry, "
            "executable fill, option P&L, PAPER, LIVE or broker authority",
            flush=True,
        )
        return 0
    except (CandidateChainCacheError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"OFFLINE QUOTE DIAGNOSTIC STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  no provider requests have been made; preserve original receipt/body evidence", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
