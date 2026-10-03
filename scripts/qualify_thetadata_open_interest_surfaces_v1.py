from __future__ import annotations

"""Run bounded read-only ThetaData open-interest surface qualification."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_open_interest_qualification_v1 import (
    run_thetadata_open_interest_qualification_v1,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only ThetaData historical open-interest qualification on the "
            "same frozen 15 anchors used by the 09:35 quote-source gate."
        )
    )
    parser.add_argument("--enrichment-plan", type=Path, required=True)
    parser.add_argument("--quote-qualification", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--authorize-provider-reads", action="store_true")
    parser.add_argument("--confirm-thetadata-standard", action="store_true")
    args = parser.parse_args(argv)

    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads for bounded read-only OI probes.",
            flush=True,
        )
        return 2
    if not args.confirm_thetadata_standard:
        print(
            "BLOCKED: confirm Options Standard before OI source qualification.",
            flush=True,
        )
        return 2

    print("ATLAS THETADATA OPEN INTEREST SURFACE QUALIFICATION V1", flush=True)
    print(
        "  READ-ONLY 15 frozen OI anchors plus one deterministic 2021 repeat. "
        "No Greeks, contract selection or option outcomes.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        plan_path = (
            args.enrichment_plan
            if args.enrichment_plan.is_absolute()
            else settings.resolved_path(args.enrichment_plan)
        )
        quote_path = (
            args.quote_qualification
            if args.quote_qualification.is_absolute()
            else settings.resolved_path(args.quote_qualification)
        )
        if plan_path.is_symlink() or not plan_path.is_file():
            raise ValueError(f"enrichment plan unavailable: {plan_path}")
        if quote_path.is_symlink() or not quote_path.is_file():
            raise ValueError(f"quote qualification unavailable: {quote_path}")
        plan = _read_object(plan_path)
        quote = _read_object(quote_path)
        _check_signature(plan, "enrichment_plan_fingerprint")
        _check_signature(quote, "qualification_fingerprint")

        report = run_thetadata_open_interest_qualification_v1(
            settings,
            plan,
            quote,
            workers=args.workers,
        )
        print(f"  enrichment_plan={plan_path}", flush=True)
        print(f"  quote_qualification={quote_path}", flush=True)
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
        print(
            f"  phase13_oi_rows_by_year={report['phase13_oi_rows_by_year']}",
            flush=True,
        )
        print(
            "  repeatability="
            f"{report['repeatability_probe'].get('deterministic_normalized_surface')}",
            flush=True,
        )
        print(f"  report={report['report_path']}", flush=True)
        print(
            "  authority "
            "greeks_authority=False single_contract_selected=False "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0 if report["full_open_interest_acquisition_source_qualified"] else 3
    except Exception as exc:
        print(
            f"THETADATA OI QUALIFICATION STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  Full OI acquisition remains unauthorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
