from __future__ import annotations

"""Run the bounded read-only ThetaData intraday option source qualification."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_intraday_option_qualification_v1 import (
    run_thetadata_intraday_option_qualification_v1,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only ThetaData Options Standard qualification over the frozen "
            "outcome-blind intraday option anchor plan."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for read-only ThetaData Terminal calls.",
    )
    parser.add_argument(
        "--confirm-thetadata-standard",
        action="store_true",
        help=(
            "Required confirmation that the operator intentionally enabled an "
            "Options Standard subscription/entitlement for this qualification."
        ),
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit bounded read-only "
            "ThetaData qualification calls.",
            flush=True,
        )
        return 2
    if not args.confirm_thetadata_standard:
        print(
            "BLOCKED: pass --confirm-thetadata-standard only after the operator "
            "has intentionally enabled Options Standard.",
            flush=True,
        )
        return 2

    print("ATLAS THETADATA INTRADAY OPTION QUALIFICATION V1", flush=True)
    print(
        "  READ-ONLY qualification anchors only. Full acquisition remains locked "
        "unless this gate proves 2021-2025 ENTRY/EXIT coverage and repeatability.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        plan_path = args.plan if args.plan.is_absolute() else settings.resolved_path(args.plan)
        if plan_path.is_symlink() or not plan_path.is_file():
            raise ValueError(f"ThetaData source plan unavailable: {plan_path}")
        plan = _read_object(plan_path)
        _check_signature(plan, "plan_fingerprint")

        report = run_thetadata_intraday_option_qualification_v1(
            settings,
            plan,
            workers=args.workers,
        )
        print(f"  plan={plan_path}", flush=True)
        print(
            "  qualification "
            f"status={report['status']} "
            f"anchors={report['qualification_anchor_count']} "
            f"provider_requests={report['provider_requests']} "
            f"hard_errors={report['hard_validation_or_transport_errors']}",
            flush=True,
        )
        print(f"  status_counts={report['status_counts']}", flush=True)
        print(
            "  oldest_2021_entry_and_exit_proven="
            f"{report['oldest_2021_entry_and_exit_proven']}",
            flush=True,
        )
        print(
            "  full_2021_2025_entry_exit_coverage_proven="
            f"{report['full_2021_2025_entry_exit_coverage_proven']}",
            flush=True,
        )
        print(
            "  repeatability="
            f"{report['repeatability_probe'].get('deterministic_normalized_row')}",
            flush=True,
        )
        for year, values in report["usable_year_role_coverage"].items():
            print(f"  year={year} usable={values}", flush=True)
        for item in report["anchors"]:
            params = item["query"]["params"]
            normalized = item.get("normalized_row") or {}
            print(
                "  anchor "
                f"{int(item['anchor_index']):03d} "
                f"status={item['status']} "
                f"reasons={','.join(item['qualification_reasons'])} "
                f"{params['symbol']} {params['expiration']} {params['strike']} "
                f"{params['start_date']} {params['time_of_day']} "
                f"staleness_seconds={normalized.get('quote_staleness_seconds')}",
                flush=True,
            )
        print(f"  report={report['report_path']}", flush=True)
        print(
            "  authority "
            f"full_acquisition_source_qualified="
            f"{report['full_acquisition_source_qualified']} "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0 if report["full_acquisition_source_qualified"] else 3
    except Exception as exc:
        print(
            f"THETADATA INTRADAY OPTION QUALIFICATION STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  Full acquisition remains unauthorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
