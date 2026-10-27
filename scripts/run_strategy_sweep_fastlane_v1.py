from __future__ import annotations

"""Run up to 64 source-isolated synthetic policy comparisons with zero provider calls.

This entrypoint deliberately cannot import ThetaData or accept source-archive paths.
It is a fixture/mechanics harness, NOT the historical market-data replay.
"""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.simulation.multiyear_offline_account_replay_v1 import (
    ORIGIN, ReplayLeg, ReplaySignal,
)
from packages.simulation.strategy_sweep_fastlane_v1 import (
    FastlaneError, StrategyFixture, run_fixture_sweep,
)


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise FastlaneError("INVALID_FIXTURE_TIMESTAMP")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FastlaneError("INVALID_FIXTURE_TIMESTAMP") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise FastlaneError("NAIVE_FIXTURE_TIMESTAMP")
    return stamp


def _leg(value: Any) -> ReplayLeg | None:
    if value is None:
        return None
    required = {
        "symbol", "kind", "entry_at_utc", "exit_at_utc",
        "entry_per_share", "exit_per_share", "multiplier", "expiration",
        "source_integrity_qualified", "observation_clock_qualified",
        "standard_deliverable_verified",
    }
    optional = {"exit_source_integrity_qualified",
                "exit_observation_clock_qualified"}
    if not isinstance(value, dict) or required - set(value) or set(value) - required - optional:
        raise FastlaneError("INVALID_FIXTURE_LEG_SCHEMA")
    if any(type(value[x]) is not bool for x in (
        "source_integrity_qualified", "observation_clock_qualified",
        "standard_deliverable_verified",
    )):
        raise FastlaneError("INVALID_FIXTURE_QUALIFICATION_FLAG")
    for key in optional:
        if key in value and value[key] is not None and type(value[key]) is not bool:
            raise FastlaneError("INVALID_FIXTURE_EXIT_FLAG")
    try:
        expiration = date.fromisoformat(value["expiration"]) if value["expiration"] is not None else None
    except (ValueError, TypeError) as exc:
        raise FastlaneError("INVALID_FIXTURE_EXPIRATION") from exc
    if type(value["multiplier"]) is not int:
        raise FastlaneError("INVALID_FIXTURE_MULTIPLIER")
    return ReplayLeg(
        symbol=value["symbol"], kind=value["kind"],
        entry_at_utc=_stamp(value["entry_at_utc"]),
        exit_at_utc=_stamp(value["exit_at_utc"]) if value["exit_at_utc"] is not None else None,
        entry_per_share=value["entry_per_share"],
        exit_per_share=value["exit_per_share"],
        multiplier=value["multiplier"], expiration=expiration,
        source_integrity_qualified=value["source_integrity_qualified"],
        observation_clock_qualified=value["observation_clock_qualified"],
        standard_deliverable_verified=value["standard_deliverable_verified"],
        exit_source_integrity_qualified=value.get("exit_source_integrity_qualified"),
        exit_observation_clock_qualified=value.get("exit_observation_clock_qualified"),
    )


def _signal(row: Any) -> ReplaySignal:
    required = {"case_id", "year", "ticker", "decision_at_utc"}
    optional = {"stock", "call", "put", "origin"}
    if not isinstance(row, dict) or required - set(row) or set(row) - required - optional:
        raise FastlaneError("INVALID_FIXTURE_SIGNAL_SCHEMA")
    if row.get("origin", ORIGIN) != ORIGIN or type(row["year"]) is not int:
        raise FastlaneError("HISTORICAL_SOURCE_NOT_ADMITTED")
    signal = ReplaySignal(
        case_id=row["case_id"], year=row["year"], ticker=row["ticker"],
        decision_at_utc=_stamp(row["decision_at_utc"]),
        stock=_leg(row.get("stock")), call=_leg(row.get("call")),
        put=_leg(row.get("put")), origin=ORIGIN,
    )
    signal.validate()
    return signal


def load_fixture_manifest(path: Path) -> tuple[list[StrategyFixture], dict]:
    if path.stat().st_size > 12 * 1024 * 1024:
        raise FastlaneError("MANIFEST_TOO_LARGE")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FastlaneError("INVALID_FIXTURE_MANIFEST_FILE") from exc
    if (not isinstance(doc, dict)
            or set(doc) != {"origin", "strategies", "policy_grid"}
            or doc["origin"] != ORIGIN
            or not isinstance(doc["strategies"], list)):
        raise FastlaneError("SYNTHETIC_FIXTURE_MANIFEST_REQUIRED")
    specs = []
    for item in doc["strategies"]:
        if not isinstance(item, dict) or set(item) != {"strategy_id", "mode", "signals"}:
            raise FastlaneError("INVALID_STRATEGY_SCHEMA")
        if not isinstance(item["signals"], list):
            raise FastlaneError("INVALID_SIGNAL_ARRAY")
        specs.append(StrategyFixture(
            strategy_id=item["strategy_id"], mode=item["mode"],
            signals=tuple(_signal(row) for row in item["signals"]),
        ))
    return specs, doc["policy_grid"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Explicit SYNTHETIC_FIXTURE_ONLY JSON experiment")
    parser.add_argument("--output", type=Path,
                        help="Optional new JSON report path; refuses overwrite")
    parser.add_argument("--no-combined", action="store_true",
                        help="Disable the same-mode shared-capital comparison")
    args = parser.parse_args(argv)
    try:
        specs, grid = load_fixture_manifest(args.manifest)
        report = run_fixture_sweep(specs, grid, include_combined=not args.no_combined)
        contents = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            if args.output.exists():
                raise FastlaneError("EXISTING_REPORT_WILL_NOT_BE_OVERWRITTEN")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as out:
                out.write(contents)
        print("ATLAS V25 RAPID OFFLINE STRATEGY SWEEP")
        print("  status=SYNTHETIC_DIAGNOSTIC_ONLY NOT_HISTORICAL")
        print(f"  strategy_count={len(specs)} scenarios={report['scenario_count']}")
        print(f"  combined_status={report['combined_status']}")
        print(f"  report_sha256={report['report_fingerprint']}")
        print("  provider_requests=0 broker_requests=0 simulations_are_fixtures=True")
        if args.output is None:
            print(contents)
        return 0
    except (FastlaneError, ValueError, OSError) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
