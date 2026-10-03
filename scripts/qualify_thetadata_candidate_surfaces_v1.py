from __future__ import annotations

"""Run bounded read-only ThetaData qualification over 09:35 candidate surfaces."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    run_thetadata_candidate_surface_qualification_v1,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only ThetaData Options Standard qualification over the frozen "
            "provider-agnostic 09:35 candidate-surface anchors."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for bounded read-only ThetaData calls.",
    )
    parser.add_argument(
        "--confirm-thetadata-standard",
        action="store_true",
        help=(
            "Required confirmation that the operator intentionally enabled an "
            "Options Standard subscription/entitlement."
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
            "BLOCKED: pass --confirm-thetadata-standard only after Options Standard "
            "has been intentionally enabled.",
            flush=True,
        )
        return 2

    print("ATLAS THETADATA CANDIDATE SURFACE QUALIFICATION V1", flush=True)
    print(
        "  READ-ONLY outcome-blind anchors only. Full 9,455-surface acquisition "
        "remains locked unless this gate proves 2021-2025 source coverage and repeatability.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        plan_path = (
            args.plan if args.plan.is_absolute() else settings.resolved_path(args.plan)
        )
        if plan_path.is_symlink() or not plan_path.is_file():
            raise ValueError(f"ThetaData candidate-surface plan unavailable: {plan_path}")
        plan = _read_object(plan_path)
        _check_signature(plan, "plan_fingerprint")

        report = run_thetadata_candidate_surface_qualification_v1(
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
            f"  valid_surface_coverage_by_year={report['valid_surface_coverage_by_year']}",
            flush=True,
        )
        print(f"  two_sided_rows_by_year={report['two_sided_rows_by_year']}", flush=True)
        print(
            "  oldest_2021_surface_proven="
            f"{report['oldest_2021_surface_proven']}",
            flush=True,
        )
        print(
            "  full_2021_2025_surface_coverage_proven="
            f"{report['full_2021_2025_surface_coverage_proven']}",
            flush=True,
        )
        print(
            "  repeatability="
            f"{report['repeatability_probe'].get('deterministic_normalized_surface')}",
            flush=True,
        )
        for item in report["anchors"]:
            params = item["query"]["params"]
            summary = item.get("surface_summary") or {}
            print(
                "  anchor "
                f"{int(item['anchor_index']):03d} "
                f"status={item['status']} "
                f"reasons={','.join(item['qualification_reasons'])} "
                f"{params['symbol']} {params['start_date']} {params['time_of_day']} "
                f"rows={summary.get('row_count')} "
                f"two_sided={summary.get('two_sided_positive_displayed_size_rows')}",
                flush=True,
            )
        print(f"  report={report['report_path']}", flush=True)
        print(
            "  authority "
            f"full_acquisition_source_qualified={report['full_acquisition_source_qualified']} "
            "single_contract_selected=False historical_fill_authority=False "
            "strategy_evidence_authority=False paper_authority=False live_authority=False",
            flush=True,
        )
        return 0 if report["full_acquisition_source_qualified"] else 3
    except Exception as exc:
        print(
            "THETADATA CANDIDATE SURFACE QUALIFICATION STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  Full acquisition remains unauthorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
