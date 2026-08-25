from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate1 import Phase25Gate1ScopeInventory  # noqa: E402
from packages.backtesting.phase25_policy import phase25_gate1_policy_fingerprint  # noqa: E402
from packages.core.settings import load_settings  # noqa: E402


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS Phase25 Gate1 provider-free PIT reference/identity scope proof"
    )
    parser.add_argument("--through", type=_date, required=True, help="final exchange session YYYY-MM-DD")
    args = parser.parse_args()

    report = Phase25Gate1ScopeInventory(load_settings()).run(through_date=args.through)
    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 1")
    print(f"Phase 25 Gate1 policy: {phase25_gate1_policy_fingerprint()}")
    print(f"Replay origin: {report['replay_origin']}")
    print(f"Through session: {report['through_date']}")
    print(f"Report: {report['report_path']}")
    print("Scope: LOCAL PIT REFERENCE / IDENTITY SCOPE PROOF ONLY")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/support authority: NONE")
    print()
    print(f"Canonical distinct symbols: {report['canonical_distinct_symbol_count']}")
    print(f"Canonical symbol-session rows: {report['canonical_symbol_session_count']}")
    print(f"Local PIT reference snapshot dates: {report['local_reference_snapshot_count']}")
    print(f"Exact first-seen reference symbols: {report['exact_first_seen_reference_symbols']}")
    print(
        "Symbols without exact first-seen reference: "
        f"{report['symbols_without_exact_first_seen_reference']}"
    )
    print(f"Distinct gap first-seen dates: {report['distinct_gap_first_seen_dates']}")
    print(f"Prior-reference-only symbols: {report['prior_reference_only_symbols']}")
    print(f"Future-only reference symbols: {report['future_only_reference_symbols']}")
    print(f"No-local-reference symbols: {report['no_local_reference_symbols']}")
    print(f"Ambiguous local identity symbols: {report['ambiguous_local_identity_symbols']}")
    print(
        "Authoritative ticker interval covers first-seen: "
        f"{report['authoritative_interval_covers_first_seen_symbols']}"
    )
    print(
        "Bounded invariant metadata proxy candidates: "
        f"{report['bounded_invariant_metadata_proxy_candidate_symbols']}"
    )
    print("Category symbol counts:")
    for key, value in report["category_symbol_counts"].items():
        print(f"  {key}: {value}")
    print("Largest first-seen evidence gaps:")
    if report["top_gap_first_seen_dates"]:
        for item in report["top_gap_first_seen_dates"][:10]:
            print(f"  {item['date']}: {item['symbols_without_exact_first_seen_reference']} symbols")
    else:
        print("  NONE")
    print(f"Recommendation: {report['recommendation']}")
    print(f"Future metadata authority: {report['future_reference_metadata_authority_allowed']}")
    print(f"Proxy support authority: {report['proxy_universe_support_authority_allowed']}")
    print(f"Protected strategy evidence reads: {report['protected_strategy_evidence_reads']}")
    print(f"Provider reads/writes: {report['provider_reads']} / {report['provider_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(
        "Order/PAPER/LIVE writes: "
        f"{report['order_writes']} / {report['paper_submits']} / {report['live_writes']}"
    )
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
