from __future__ import annotations

"""Build the zero-provider ThetaData intraday option source plan."""

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
from packages.data.thetadata_intraday_option_plan_v1 import (
    OUTPUT_REL,
    PROVIDER_CANDIDATE,
    build_thetadata_intraday_option_source_plan,
)


class ThetaDataPlanRunnerError(ValueError):
    pass


def _persist(settings, report: dict) -> tuple[Path, str]:
    fingerprint = report["plan_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fingerprint[:16]}.json")
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != encoded:
            raise ThetaDataPlanRunnerError("existing immutable ThetaData source plan differs")
        return path, "REUSED_IDENTICAL_THETADATA_INTRADAY_OPTION_PLAN"
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != encoded:
        raise ThetaDataPlanRunnerError("ThetaData source plan write/readback failed")
    return path, "WRITTEN_IMMUTABLE_THETADATA_INTRADAY_OPTION_PLAN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan an outcome-blind ThetaData Options Value qualification and exact "
            "intraday historical option NBBO acquisition shape. Zero provider reads."
        )
    )
    parser.add_argument(
        "--intraday-clock",
        type=Path,
        required=True,
        help="Exact immutable multiyear_intraday_stock_exit_clock_v1 artifact.",
    )
    args = parser.parse_args(argv)

    print("ATLAS THETADATA INTRADAY OPTION SOURCE PLAN V1", flush=True)
    print(
        "  ZERO provider GETs. No subscription required for this step. "
        "Consumes only the immutable intraday stock-exit clock artifact.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")

        source_path = (
            args.intraday_clock
            if args.intraday_clock.is_absolute()
            else settings.resolved_path(args.intraday_clock)
        )
        if source_path.is_symlink() or not source_path.is_file():
            raise ThetaDataPlanRunnerError("intraday clock artifact unavailable")
        source = _read_object(source_path)
        _check_signature(source, "intraday_clock_fingerprint")

        report = build_thetadata_intraday_option_source_plan(source)
        output_path, action = _persist(settings, report)

        scope = report["target_scope"]
        shape = report["request_shape_analysis"]
        qualification = report["qualification"]

        print(f"  intraday_clock={source_path}", flush=True)
        print(
            "  provider_candidate "
            f"provider={PROVIDER_CANDIDATE['provider']} "
            f"tier={PROVIDER_CANDIDATE['target_subscription']} "
            f"observed_monthly_price_usd="
            f"{PROVIDER_CANDIDATE['retail_monthly_price_usd_observed']} "
            f"concurrency={PROVIDER_CANDIDATE['documented_concurrent_requests_observed']}",
            flush=True,
        )
        print(
            "  target_scope "
            f"cases={scope['case_members']} "
            f"exact_queries={scope['exact_at_time_nbbo_queries']} "
            f"date_min={scope['date_min']} "
            f"date_max={scope['date_max']} "
            f"minute_aligned={scope['minute_boundary_aligned']}",
            flush=True,
        )
        print(f"  by_year={scope['by_year']}", flush=True)
        print(f"  role_memberships={scope['role_memberships']}", flush=True)
        print(
            "  request_shape "
            f"contract_day_groups={shape['unique_contract_day_groups']} "
            f"groups_with_multiple_clocks="
            f"{shape['contract_day_group_size']['groups_with_multiple_exact_clocks']} "
            f"history_row_upper_bound="
            f"{shape['one_minute_history_min_to_max_row_upper_bound']}",
            flush=True,
        )
        print(
            "  qualification "
            f"anchors={qualification['anchor_query_count']} "
            "full_acquisition_authorized=False",
            flush=True,
        )
        for item in qualification["anchors"]:
            q = item["query"]
            params = q["params"]
            print(
                "    "
                f"[{item['anchor_index']:02d}] "
                f"reasons={','.join(item['qualification_reasons'])} "
                f"{params['symbol']} {params['expiration']} "
                f"{params['strike']} {params['right']} "
                f"{params['start_date']} {params['time_of_day']}",
                flush=True,
            )
        print(f"  source_plan={action} / {output_path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 provider_writes=0 "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"THETADATA INTRADAY OPTION SOURCE PLAN STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider fallback or paid request is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
