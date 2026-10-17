from __future__ import annotations

"""Zero-provider-read preflight for the isolated ThetaData Python-library worker."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.providers.thetadata.preflight import run_thetadata_preflight_v1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate isolated ThetaData provider Python, pinned library version, "
            "authentication source and immutable ATLAS plan linkage. Makes zero "
            "ThetaData market-data requests."
        )
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--enrichment-plan", type=Path, required=True)
    parser.add_argument(
        "--provider-python",
        type=Path,
        help=(
            "Optional isolated provider Python override. Default is "
            ".provider_venvs/thetadata under the ATLAS repository."
        ),
    )
    args = parser.parse_args(argv)

    print("ATLAS THETADATA ISOLATED PYTHON PREFLIGHT V1", flush=True)
    print(
        "  ZERO provider requests. No Theta Terminal or Java required.",
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

        result = run_thetadata_preflight_v1(
            source_plan=_read_object(source_path),
            enrichment_plan=_read_object(enrichment_path),
            provider_python=args.provider_python,
        )
        print(
            "  provider_python "
            f"path={result.provider_python} "
            f"present={result.provider_python_present} "
            f"version={result.provider_python_version} "
            f"meets_3_12_plus={result.provider_python_meets_3_12}",
            flush=True,
        )
        print(
            "  library "
            f"installed={result.library_installed} "
            f"version={result.library_version} "
            f"tested={result.tested_library_version} "
            f"matches_tested={result.library_version_matches_tested} "
            f"environment={str(result.provider_environment_fingerprint)[:16]}",
            flush=True,
        )
        print(
            "  auth "
            f"source={result.auth_source} "
            f"material_present={result.auth_material_present}",
            flush=True,
        )
        print(
            "  plans "
            f"source_valid={result.source_plan_valid} "
            f"enrichment_valid={result.enrichment_plan_valid} "
            f"linked={result.plans_linked}",
            flush=True,
        )
        for item in result.detail:
            print(f"  detail: {item}", flush=True)
        print(
            "  COMPLETE "
            f"provider_requests={result.provider_requests} "
            f"ready={result.ready_for_bounded_source_qualification} "
            f"next_action={result.next_action}",
            flush=True,
        )
        return 0 if result.ready_for_bounded_source_qualification else 4
    except Exception as exc:
        print(
            f"THETADATA PYTHON PREFLIGHT STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No ThetaData market-data request was attempted.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
