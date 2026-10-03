from __future__ import annotations

"""Plan ThetaData candidate-surface qualification from the accepted 09:35 artifact."""

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
from packages.data.thetadata_candidate_surface_plan_v1 import (
    OUTPUT_REL,
    build_thetadata_candidate_surface_source_plan,
)


def _persist(settings, report: dict) -> tuple[Path, str]:
    fp = report["plan_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fp[:16]}.json")
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise ValueError("existing immutable ThetaData candidate-surface plan differs")
        return path, "REUSED_IDENTICAL_THETADATA_SURFACE_PLAN"
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != raw:
        raise ValueError("ThetaData candidate-surface plan write/readback failed")
    return path, "WRITTEN_IMMUTABLE_THETADATA_SURFACE_PLAN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the zero-provider ThetaData candidate-surface qualification plan "
            "from the accepted 09:35 option-decision-spot artifact."
        )
    )
    parser.add_argument("--decision-spot", type=Path, required=True)
    args = parser.parse_args(argv)

    print("ATLAS THETADATA CANDIDATE SURFACE PLAN V1", flush=True)
    print(
        "  ZERO provider GETs. No strike/expiration preselection. "
        "Maps each accepted 09:35 underlying/date key to one bounded CALL surface request.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        source = (
            args.decision_spot
            if args.decision_spot.is_absolute()
            else settings.resolved_path(args.decision_spot)
        )
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"decision-spot artifact unavailable: {source}")
        decision = _read_object(source)
        _check_signature(decision, "decision_spot_fingerprint")
        report = build_thetadata_candidate_surface_source_plan(decision)
        path, action = _persist(settings, report)

        scope = report["target_scope"]
        provider = report["provider_candidate"]
        print(f"  decision_spot={source}", flush=True)
        print(
            "  target "
            f"ready_cases={scope['decision_spot_ready_cases']} "
            f"missing={scope['decision_spot_missing_cases']} "
            f"surface_requests={scope['unique_surface_requests']} "
            f"underlyings={scope['unique_underlyings']} "
            f"date_range={scope['date_min']}..{scope['date_max']}",
            flush=True,
        )
        print(f"  by_year={scope['by_year']}", flush=True)
        print(
            "  provider_candidate "
            f"{provider['target_subscription']} "
            f"concurrency={provider['documented_concurrent_requests_observed']} "
            f"history={provider['retail_history_marketing_observed']} "
            f"endpoint={provider['at_time_endpoint']}",
            flush=True,
        )
        print(
            "  request_shape "
            "expiration=* strike=* right=call "
            f"max_dte={scope['max_dte_calendar_days']} "
            "strike_range=None",
            flush=True,
        )
        print(
            f"  qualification_anchors={report['qualification']['anchor_query_count']}",
            flush=True,
        )
        print(f"  plan={action} / {path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 full_acquisition_authorized=False "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"THETADATA CANDIDATE SURFACE PLAN STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider request or fallback is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
