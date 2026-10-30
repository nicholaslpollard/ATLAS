from __future__ import annotations

"""V44 source-backed SPY alternate-contract recovery; not a trading simulation.

For the 174 original V43 OI-failing source-selected dates, first use already
archived decision-morning OI + previous 09:59 SPY spot to choose a new contract
without future quote/exit information. On discovery, ask the V39/V38 cache for
both rights at 09:59 (pre-decision) and 10:01 (hypothetical order clock).
The cache may dispatch required ThetaData reads and persist the exact source.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.spy_alternate_oi_contract_recovery_v44 import (
    assess_alternate_quotes, build_report, discover_alternate, oi_recovery_targets,
    oi_surface_demand, quote_demands, verified_original_cases,
)
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands
from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor

V43_MAX_BYTES = 4 * 1024 * 1024
VERSION = "spy_v44_alternate_predecision_oi_variant"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v43", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    print("ATLAS V44 CAUSAL SPY ALTERNATE OI CONTRACT AND TWO-CLOCK SOURCE RECOVERY", flush=True)
    print("  original_v43=IMMUTABLE options_data=REUSE_OR_FETCH_ARCHIVE automatically", flush=True)
    try:
        if (args.v43.is_symlink() or not args.v43.is_file()
                or not 0 < args.v43.stat().st_size <= V43_MAX_BYTES):
            raise ValueError("V44_INPUT_REPORT_MISSING_OR_OVERSIZED")
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("V44_REPORT_ALREADY_PRESENT")
        v43 = json.loads(args.v43.read_text(encoding="utf-8"))
        originals = verified_original_cases(v43)
        targets = oi_recovery_targets(originals)
        settings = load_settings(ROOT, "development")
        if not targets:
            raise ValueError("V44_NO_OI_RECOVERY_TARGETS")
        print(f"  original_cases={len(originals)} OI_failed_recovery_dates={len(targets)}", flush=True)
        print("  PHASE_1: prior morning OI + 09:59 SPY spot; select a new 30-45DTE strike/expiry", flush=True)
        recovered = {}
        def read_oi(item, source):
            day = item["kwargs"]["date_et"]
            # The returned OI source surface is only held during this
            # callback; output keeps selected exact original OI observations.
            case = next(c for c in targets if c["date_et"] == day)
            recovered[day] = discover_alternate(case, source)

        with SourceProgressMonitor(expected_source_uses=len(targets)) as progress:
            oi_run = resolve_strategy_source_demands(
                settings, VERSION, (oi_surface_demand(c) for c in targets),
                on_source=read_oi, on_progress=progress.event,
                continue_on_error=True,
            )
        for row in targets:
            if row["date_et"] not in recovered:
                recovered[row["date_et"]] = {
                    "date_et": row["date_et"], "status": "OI_SOURCE_UNAVAILABLE",
                    "original_expiration": row["expiration"],
                    "original_strike": row["strike"],
                    "reason": "RETRYABLE_OI_SOURCE_UNRESOLVED",
                    "historical_signal": None, "historical_fill": None,
                    "actual_pnl": None,
                }
        selected = sorted(
            (r for r in recovered.values()
             if r["status"] == "ALTERNATE_FROM_PRIOR_STATE_OI"),
            key=lambda c: c["date_et"],
        )
        print(f"  PHASE_1_COMPLETE: alternate_contracts_selected={len(selected)}"
              f" no_alternate_or_unresolved={len(targets)-len(selected)}"
              f" provider_attempts={oi_run['provider_dispatch_attempts']}"
              f" cached={oi_run['persisted_cache_hits']}", flush=True)
        quote_run = {
            "source_uses_requested": 0, "source_uses_resolved": 0,
            "source_uses_failed_or_unresolved": 0,
            "provider_dispatch_attempts": 0,
            "provider_fetch_successes": 0, "persisted_cache_hits": 0,
        }
        if selected:
            print(f"  PHASE_2: exact alternate 09:59 and 10:01 call/put quotes,"
                  f" planned_source_uses={len(selected)*4}", flush=True)
            quotes = {}
            for item in selected:
                quotes[item["date_et"]] = {}

            def receive(item, source):
                day = item["kwargs"]["date_et"]
                quotes[day][item["purpose"]] = (item, source)

            def demands():
                for candidate in selected:
                    yield from quote_demands(candidate)

            with SourceProgressMonitor(expected_source_uses=len(selected) * 4) as progress:
                quote_run = resolve_strategy_source_demands(
                    settings, VERSION, demands(), on_source=receive,
                    on_progress=progress.event, continue_on_error=True,
                )
            for item in selected:
                recovered[item["date_et"]] = assess_alternate_quotes(
                    item, quotes[item["date_et"]],
                )
        result = build_report(
            v43, [recovered[day] for day in sorted(recovered)],
            [oi_run, quote_run],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True, allow_nan=False)
            out.write("\n")
        for status, count in sorted(result["recovery_status_counts"].items()):
            print(f"  {status}={count}", flush=True)
        print(f"  provider_attempts_total={oi_run['provider_dispatch_attempts']+quote_run['provider_dispatch_attempts']}"
              f" cached_total={oi_run['persisted_cache_hits']+quote_run['persisted_cache_hits']}"
              f" new_archives={oi_run['provider_fetch_successes']+quote_run['provider_fetch_successes']}"
              f" source_failures={oi_run['source_uses_failed_or_unresolved']+quote_run['source_uses_failed_or_unresolved']}", flush=True)
        print(f"  fingerprint={result['fingerprint']} saved={args.output}", flush=True)
        print("  COMPLETE: ALTERNATE_VARIANT_SOURCE_EVIDENCE_ONLY; NOT_HISTORICAL_TRADES", flush=True)
        return 0 if (oi_run["source_uses_failed_or_unresolved"] +
                     quote_run["source_uses_failed_or_unresolved"]) == 0 else 2
    except (ValueError, KeyError, OSError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:350]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
