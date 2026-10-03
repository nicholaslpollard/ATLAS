from __future__ import annotations

"""Run or preview the qualified ThetaData 09:35 candidate-surface cache."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_cache_v1 import (
    run_thetadata_candidate_surface_cache_v1,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or acquire the qualified ThetaData 09:35 candidate surfaces. "
            "Default is zero-network preview."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--max-new-requests", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required for any positive --max-new-requests.",
    )
    args = parser.parse_args(argv)

    print("ATLAS THETADATA CANDIDATE SURFACE CACHE V1", flush=True)
    print(
        "  Resumable D:-bound raw surface cache. Zero-network preview unless "
        "--authorize-provider-reads and a positive request cap are both supplied.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        plan_path = args.plan if args.plan.is_absolute() else settings.resolved_path(args.plan)
        qualification_path = (
            args.qualification
            if args.qualification.is_absolute()
            else settings.resolved_path(args.qualification)
        )
        if plan_path.is_symlink() or not plan_path.is_file():
            raise ValueError(f"ThetaData source plan unavailable: {plan_path}")
        if qualification_path.is_symlink() or not qualification_path.is_file():
            raise ValueError(
                f"ThetaData source qualification unavailable: {qualification_path}"
            )
        plan = _read_object(plan_path)
        qualification = _read_object(qualification_path)
        _check_signature(plan, "plan_fingerprint")
        _check_signature(qualification, "qualification_fingerprint")

        report = run_thetadata_candidate_surface_cache_v1(
            settings,
            plan,
            qualification,
            max_new_requests=args.max_new_requests,
            workers=args.workers,
            authorize_provider_reads=args.authorize_provider_reads,
        )
        print(f"  plan={plan_path}", flush=True)
        print(f"  qualification={qualification_path}", flush=True)
        print(
            "  cache "
            f"status={report['status']} "
            f"total={report['candidate_surface_requests']} "
            f"cached_complete={report['verified_cached_complete']} "
            f"cached_no_data={report['verified_cached_no_data']} "
            f"new_attempts={report['new_provider_attempts']} "
            f"new_complete={report['new_complete']} "
            f"new_no_data={report['new_no_data']} "
            f"pending={report.get('pending_after_run', report['pending_before_run'])}",
            flush=True,
        )
        print(
            f"  new_raw_bytes={report['new_raw_bytes']} workers={report['workers']} "
            f"max_new_requests={report['max_new_requests']}",
            flush=True,
        )
        print(
            "  authority single_contract_selected=False option_exit_prices_read=0 "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"THETADATA CANDIDATE SURFACE CACHE STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  Preserve all existing raw receipts/intents. Do not blindly retry an "
            "uncertain provider attempt.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
