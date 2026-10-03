from __future__ import annotations

"""Build the zero-provider ThetaData quote-surface enrichment plan."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    OUTPUT_REL,
    build_thetadata_surface_enrichment_plan,
)


def _persist(settings, report: dict) -> tuple[Path, str]:
    fp = report["enrichment_plan_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fp[:16]}.json")
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise ValueError("existing immutable ThetaData enrichment plan differs")
        return path, "REUSED_IDENTICAL_THETADATA_ENRICHMENT_PLAN"
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return path, "WRITTEN_IMMUTABLE_THETADATA_ENRICHMENT_PLAN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze zero-provider historical open-interest surface demand and "
            "downstream dividend-aware binomial-Greeks policy."
        )
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    args = parser.parse_args(argv)

    print("ATLAS THETADATA SURFACE ENRICHMENT PLAN V1", flush=True)
    print(
        "  ZERO provider GETs. Adds historical OI surfaces and freezes the "
        "quote+OI -> expiration-specific dividend-aware binomial-Greeks pipeline.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        source = args.source_plan if args.source_plan.is_absolute() else settings.resolved_path(args.source_plan)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"ThetaData source plan unavailable: {source}")
        plan = _read_object(source)
        _check_signature(plan, "plan_fingerprint")
        report = build_thetadata_surface_enrichment_plan(plan)
        path, action = _persist(settings, report)

        oi = report["open_interest_stage"]
        greeks = report["greeks_stage"]
        print(f"  source_plan={source}", flush=True)
        print(
            f"  open_interest requests={oi['request_count']} by_year={oi['by_year']} "
            f"endpoint={oi['endpoint']}",
            flush=True,
        )
        print(
            "  pre_greeks_filter "
            f"dte={report['pre_greeks_filter']['dte_calendar_days']} "
            f"min_oi={report['pre_greeks_filter']['minimum_open_interest']} "
            f"max_spread_to_mid={report['pre_greeks_filter']['maximum_spread_to_mid']}",
            flush=True,
        )
        print(
            "  greeks "
            f"endpoint={greeks['endpoint']} model={greeks['provider_model']} "
            f"clock={greeks['start_time']} interval={greeks['interval']} "
            f"version={greeks['version']} steps={greeks['binomial_steps']}",
            flush=True,
        )
        print(
            "  dividend_policy=REQUIRED_PIT_INPUT_NO_SILENT_ZERO_DEFAULT "
            "greeks_requests=DEFERRED_UNTIL_QUOTE_OI_SURVIVORS",
            flush=True,
        )
        print(f"  plan={action} / {path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 single_contract_selected=False "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"THETADATA SURFACE ENRICHMENT PLAN STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider request or source fallback is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
