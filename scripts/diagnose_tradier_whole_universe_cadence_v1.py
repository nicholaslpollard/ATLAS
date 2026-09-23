from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.tradier_whole_universe_cadence import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_tradier_whole_universe_cadence_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Tradier whole-universe cadence/freshness diagnostic. "
            "Measures repeated broad snapshots plus bounded unresolved-symbol retries."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for read-only Tradier market-data calls.",
    )
    parser.add_argument(
        "--run-live-cadence-diagnostic",
        action="store_true",
        help=(
            "Required second gate acknowledging the diagnostic will run for about "
            "10 minutes and issue up to 40 read-only provider calls."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit read-only "
            "Tradier current-market-data calls."
        )
        return 2
    if not args.run_live_cadence_diagnostic:
        print(
            "BLOCKED: pass --run-live-cadence-diagnostic to acknowledge the "
            "bounded multi-pass live diagnostic."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")

    print("ATLAS Tradier Whole-Universe Cadence Diagnostic V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print("  environment: production")
    print("  endpoint: POST /v1/markets/quotes")
    print(
        "  schedule: "
        f"{CONTRACT['cycles']} broad cycles / "
        f"{CONTRACT['broad_interval_seconds']}s spacing / "
        f"+{CONTRACT['retry_delay_seconds']}s unresolved retry"
    )
    print(f"  max provider reads: {CONTRACT['max_provider_reads']}")
    print("  current population: Alpaca SIP V2 active + tradable + us_equity")
    print("  optional Phase 7 subset metrics: enabled when local snapshot exists")
    print("  raw gzip response preservation: enabled")
    print("  live tracker: enabled")
    print("  provider writes: 0")
    print("  broker reads/writes: 0/0")
    print("  order authority: false")
    print("  PAPER/LIVE authority: false")
    print("  strategy/provider-policy authority: false")
    print(
        "  NOTE: quote-age/spread thresholds are diagnostic sensitivity only; "
        "this run does not freeze production cadence or gates"
    )

    report = run_tradier_whole_universe_cadence_v1(settings)

    print("\nTRADIER WHOLE-UNIVERSE CADENCE: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    population = dict(report["population"])
    print(
        "  population: "
        f"{int(population['symbol_count']):,} symbols / "
        f"sha256={population['sha256']}"
    )
    print(
        "  Phase 7 subset: "
        f"available={population['phase7_available']} "
        f"as_of={population['phase7_as_of']} "
        f"symbols={population['phase7_symbol_count']}"
    )
    print(
        "  completed: "
        f"broad={int(report['broad_cycles_completed'])}/{CONTRACT['cycles']} "
        f"retry={int(report['retry_cycles_completed'])} "
        f"provider_reads={int(report['provider_reads'])}"
    )
    print(f"  wall seconds: {float(report['wall_seconds']):.1f}")
    print(
        "  persistent missing: "
        f"{int(dict(report['persistent_missing'])['count']):,}"
    )
    print(
        "  ever missing: "
        f"{int(dict(report['ever_missing'])['count']):,}"
    )
    print("  cadence views:")
    for seconds, item in dict(report["cadence_views"]).items():
        values = dict(item)
        print(
            f"    {seconds}s: "
            f"pairs={values['comparison_pairs']} "
            f"quote_advanced={values['quote_timestamp_advanced_fraction']} "
            f"missing_recovered={values['missing_recovered_by_later_broad_fraction']}"
        )

    if report["broad"]:
        first = dict(report["broad"][0])
        last = dict(report["broad"][-1])
        print(
            "  first broad: "
            f"coverage={float(first['coverage_fraction']):.3%} "
            f"quote<=30s={dict(first['quote_age_counts'])['30']:,} "
            f"usable30/100={int(first['diagnostic_usable_30s_100bps_count']):,} "
            f"missing={int(first['missing_count']):,}"
        )
        print(
            "  last broad: "
            f"coverage={float(last['coverage_fraction']):.3%} "
            f"quote<=30s={dict(last['quote_age_counts'])['30']:,} "
            f"usable30/100={int(last['diagnostic_usable_30s_100bps_count']):,} "
            f"missing={int(last['missing_count']):,}"
        )

    if report["retries"]:
        total_missing_recovered = sum(
            int(dict(item["recovery"])["missing_recovered"])
            for item in report["retries"]
        )
        total_freshness_recovered = sum(
            int(dict(item["recovery"])["freshness_recovered"])
            for item in report["retries"]
        )
        print(
            "  retry recoveries across cycles: "
            f"missing={total_missing_recovered:,} "
            f"freshness={total_freshness_recovered:,}"
        )

    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: diagnostic only; no cadence, provider policy, strategy, "
        "PAPER or LIVE authority created"
    )
    return 0 if report["status"] != "FAIL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
