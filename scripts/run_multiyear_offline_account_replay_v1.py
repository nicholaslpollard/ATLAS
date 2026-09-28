from __future__ import annotations

"""Offline source-admission census and explicitly synthetic account smoke test."""

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.simulation.multiyear_account_readiness_v1 import (
    AccountReadinessError, EXPECTED_SOURCE_FP,
    build_replay_readiness, persist_replay_readiness,
)
from packages.simulation.multiyear_offline_account_replay_v1 import (
    OfflineAccountReplayError, ReplayLeg, ReplayPolicy, ReplaySignal,
    compare_synthetic_modes,
)

CASEBOOK = Path(
    "data/options/derived/"
    "multiyear_verified_stock_option_source_casebook_v1_176aa0427a9ec34f.json"
)


def _fixture() -> list[ReplaySignal]:
    """Only fabricated prices and timestamps; never the accepted historical source."""
    a, b, c = (
        datetime(2022, 1, 3, 14, 35, tzinfo=UTC),
        datetime(2022, 1, 4, 21, 0, tzinfo=UTC),
        datetime(2022, 1, 5, 21, 0, tzinfo=UTC),
    )
    def leg(kind, symbol, entry, exit_, multiplier, expiration):
        return ReplayLeg(
            symbol=symbol, kind=kind, entry_at_utc=b, exit_at_utc=c,
            entry_per_share=entry, exit_per_share=exit_,
            multiplier=multiplier, expiration=expiration,
            source_integrity_qualified=True, observation_clock_qualified=True,
            standard_deliverable_verified=True,
        )
    return [
        ReplaySignal(
            case_id="SYNTHETIC-CASE-ONE", year=2022, ticker="TEST", decision_at_utc=a,
            stock=leg("STOCK", "TEST", "100", "102", 1, None),
            call=leg("CALL", "O:TEST220121C00100000", "2.00", "3.00", 100, date(2022, 1, 21)),
            put=leg("PUT", "O:TEST220121P00100000", "1.80", "0.70", 100, date(2022, 1, 21)),
        ),
        ReplaySignal(
            case_id="SYNTHETIC-CASE-TWO", year=2022, ticker="XYZ", decision_at_utc=a,
            stock=leg("STOCK", "XYZ", "50", "49", 1, None),
            call=None, put=None,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS strict zero-GET full-population replay readiness and synthetic engine"
    )
    parser.add_argument("--casebook", type=Path, default=CASEBOOK)
    parser.add_argument("--expected-source-fingerprint", default=EXPECTED_SOURCE_FP,
                        help="Exact approved immutable casebook SHA for a later new source cohort")
    parser.add_argument("--synthetic-smoke", action="store_true",
                        help="Additionally run all four account modes with invented test prices")
    args = parser.parse_args()
    print("ATLAS MULTIYEAR OFFLINE ACCOUNT ENGINE — NO PROVIDER CALLS", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        book = _read_object(args.casebook)
        report = build_replay_readiness(
            book, expected_source_fp=args.expected_source_fingerprint,
        )
        path, status = persist_replay_readiness(settings, report)
        print(f"  signed_source={report['source_casebook_fingerprint']}", flush=True)
        print(f"  original_cases={report['original_case_denominator']}", flush=True)
        print(f"  original_right_slots={report['original_right_memberships']}", flush=True)
        print(f"  dated_option_and_stock_sources={report['dated_option_stock_source_rights']}", flush=True)
        print(f"  actual_synchronized_eligible_option_trades={report['actual_executable_option_trades']}", flush=True)
        for year, counts in report["by_year"].items():
            print(f"  year_{year}={counts}", flush=True)
        print(f"  source_readiness={status} / {path}", flush=True)
        print(f"  readiness_fingerprint={report['readiness_fingerprint']}", flush=True)
        if args.synthetic_smoke:
            print("  SYNTHETIC FIXTURE ACCOUNT MECHANICS — NOT HISTORICAL PRICES", flush=True)
            simulated = compare_synthetic_modes(
                _fixture(), policy=ReplayPolicy(max_open_positions=1),
            )
            for mode, output in simulated.items():
                print(
                    f"    synthetic_{mode}=cases:{output['original_case_denominator']} "
                    f"modeled_round_trips:{output['synthetic_round_trips']} "
                    f"ending_cash:{output['ending_cash']} "
                    f"fingerprint:{output['replay_fingerprint']}",
                    flush=True,
                )
        print("  Historical P&L remains NULL; no fabricated same-clock evidence or fills.", flush=True)
        return 0
    except (AccountReadinessError, OfflineAccountReplayError, ValueError,
            KeyError, TypeError, OSError) as exc:
        print(f"OFFLINE ACCOUNT REPLAY GATE STOPPED: {type(exc).__name__}: {exc}",
              flush=True)
        print("  Existing source receipts unchanged; no provider fallback.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
