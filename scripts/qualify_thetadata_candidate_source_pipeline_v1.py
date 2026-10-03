from __future__ import annotations

"""Qualify ThetaData quote and open-interest surfaces in one bounded source gate."""

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
from packages.data.thetadata_open_interest_qualification_v1 import (
    run_thetadata_open_interest_qualification_v1,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded read-only ThetaData source qualification: causal 09:35 quote "
            "surfaces first, then previous-session open-interest surfaces on the "
            "same frozen 15 anchors."
        )
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--enrichment-plan", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--authorize-provider-reads", action="store_true")
    parser.add_argument("--confirm-thetadata-standard", action="store_true")
    args = parser.parse_args(argv)

    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads for bounded ThetaData source probes.",
            flush=True,
        )
        return 2
    if not args.confirm_thetadata_standard:
        print(
            "BLOCKED: confirm Options Standard before ThetaData source qualification.",
            flush=True,
        )
        return 2

    print("ATLAS THETADATA CANDIDATE SOURCE QUALIFICATION PIPELINE V1", flush=True)
    print(
        "  READ-ONLY. Stage 1: 15 quote anchors + deterministic 2021 repeat. "
        "Stage 2: 15 OI anchors + deterministic 2021 repeat. "
        "At most 32 provider requests; no Greeks or option outcomes.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        source_path = (
            args.source_plan
            if args.source_plan.is_absolute()
            else settings.resolved_path(args.source_plan)
        )
        enrichment_path = (
            args.enrichment_plan
            if args.enrichment_plan.is_absolute()
            else settings.resolved_path(args.enrichment_plan)
        )
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError(f"ThetaData source plan unavailable: {source_path}")
        if enrichment_path.is_symlink() or not enrichment_path.is_file():
            raise ValueError(
                f"ThetaData enrichment plan unavailable: {enrichment_path}"
            )
        source = _read_object(source_path)
        enrichment = _read_object(enrichment_path)
        _check_signature(source, "plan_fingerprint")
        _check_signature(enrichment, "enrichment_plan_fingerprint")
        if enrichment.get("source_plan_fingerprint") != source["plan_fingerprint"]:
            raise ValueError("ThetaData enrichment/source plan fingerprint mismatch")

        quote = run_thetadata_candidate_surface_qualification_v1(
            settings,
            source,
            workers=args.workers,
        )
        print(
            "  quote "
            f"status={quote['status']} "
            f"requests={quote['provider_requests']} "
            f"hard_errors={quote['hard_validation_or_transport_errors']} "
            f"repeatability={quote['repeatability_probe'].get('deterministic_normalized_surface')}",
            flush=True,
        )
        print(f"  quote_report={quote['report_path']}", flush=True)
        if not quote["full_acquisition_source_qualified"]:
            print(
                "  STOP: quote source did not qualify; OI source was not contacted.",
                flush=True,
            )
            return 3

        oi = run_thetadata_open_interest_qualification_v1(
            settings,
            enrichment,
            quote,
            workers=args.workers,
        )
        print(
            "  open_interest "
            f"status={oi['status']} "
            f"requests={oi['provider_requests']} "
            f"hard_errors={oi['hard_validation_or_transport_errors']} "
            f"repeatability={oi['repeatability_probe'].get('deterministic_normalized_surface')}",
            flush=True,
        )
        print(f"  oi_report={oi['report_path']}", flush=True)
        print(
            "  combined "
            f"provider_requests={quote['provider_requests'] + oi['provider_requests']} "
            f"quote_qualified={quote['full_acquisition_source_qualified']} "
            f"oi_qualified={oi['full_open_interest_acquisition_source_qualified']}",
            flush=True,
        )
        print(
            "  authority greeks=False contract_selection=False option_outcomes=False "
            "historical_fill=False strategy=False paper=False live=False",
            flush=True,
        )
        return 0 if oi["full_open_interest_acquisition_source_qualified"] else 3
    except Exception as exc:
        print(
            "THETADATA CANDIDATE SOURCE QUALIFICATION PIPELINE STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  Preserve any raw receipts already written. Full acquisition remains locked.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
