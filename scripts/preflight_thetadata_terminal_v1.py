from __future__ import annotations

"""Zero-market-data preflight for the local ThetaData v3 Terminal."""

import argparse
import json
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
            "Validate Java 21+, loopback Theta Terminal reachability, local auth "
            "signals, and immutable ATLAS source/enrichment plan linkage. "
            "Makes zero market-data/provider HTTP requests."
        )
    )
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--enrichment-plan", type=Path, required=True)
    parser.add_argument(
        "--terminal-dir",
        type=Path,
        help=(
            "Optional directory containing ThetaTerminalv3.jar and auth .env/creds.txt. "
            "Secrets are never printed."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=25503)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also emit a machine-readable result JSON object.",
    )
    args = parser.parse_args(argv)

    print("ATLAS THETADATA TERMINAL PREFLIGHT V1", flush=True)
    print(
        "  ZERO market-data requests. Checks Java, loopback Terminal socket, "
        "auth-source presence and immutable ATLAS plan linkage only.",
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
            terminal_dir=args.terminal_dir,
            host=args.host,
            port=args.port,
        )
        print(
            "  java "
            f"found={result.java_found} major={result.java_major} "
            f"meets_21_plus={result.java_meets_minimum}",
            flush=True,
        )
        print(
            "  terminal "
            f"{result.terminal_host}:{result.terminal_port} "
            f"reachable={result.terminal_reachable}",
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
        if args.json:
            print(json.dumps(result.to_dict(), sort_keys=True), flush=True)
        return 0 if result.ready_for_bounded_source_qualification else 4
    except Exception as exc:
        print(
            f"THETADATA TERMINAL PREFLIGHT STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No market-data request was attempted.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
