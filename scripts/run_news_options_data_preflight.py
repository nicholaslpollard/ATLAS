from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.news_options_source_preflight import (
    run_news_options_data_preflight,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect ATLAS news/options research storage and optionally probe "
            "historical provider entitlements without bulk downloading data."
        )
    )
    parser.add_argument(
        "--initialize-layout",
        action="store_true",
        help="Create the bounded news/options research directory layout.",
    )
    parser.add_argument(
        "--probe-providers",
        action="store_true",
        help=(
            "Perform tiny read-only Alpaca news, Massive option-reference and "
            "Massive S3 prefix probes. No bulk downloads are performed."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional preflight JSON output path.",
    )
    return parser


def _fmt_status(item: object) -> str:
    if not isinstance(item, dict):
        return "n/a"
    status = str(item.get("status") or "n/a")
    code = item.get("http_status")
    return f"{status} ({code})" if code is not None else status


def main() -> int:
    args = _parser().parse_args()
    settings = load_settings(PROJECT_ROOT)
    report = run_news_options_data_preflight(
        settings,
        initialize_layout=args.initialize_layout,
        probe_providers=args.probe_providers,
        output_path=args.output,
    )

    storage = report["storage"]
    print("ATLAS News + Options Data Foundation Preflight")
    print(f"  fingerprint: {report['fingerprint']}")
    print(f"  disk free: {float(storage['disk_free_gib']):.2f} GiB")
    print(f"  storage status: {storage['status']}")
    print(
        "  research budget: "
        f"{float(storage['acquisition_budget_gib']):.2f} GiB total / "
        f"{float(storage['remaining_acquisition_budget_gib']):.2f} GiB remaining"
    )
    print(
        "  maximum safe additional now: "
        f"{float(storage['maximum_safe_additional_gib']):.2f} GiB"
    )
    print(
        "  minimum/warning free space: "
        f"{float(storage['minimum_free_gib']):.2f} / "
        f"{float(storage['warning_free_gib']):.2f} GiB"
    )
    print("\n  Category usage / quota:")
    for name, quota in storage["category_quota_gib"].items():
        used = float(storage["category_usage_gib"].get(name, 0.0))
        print(f"    {name}: {used:.3f} / {float(quota):.2f} GiB")

    probes = report["provider_probes"]
    if probes.get("performed"):
        print("\n  Provider probes (read-only, no bulk download):")
        print(
            "    Alpaca historical news 2015: "
            + _fmt_status(probes.get("alpaca_historical_news"))
        )
        print(
            "    Massive 2016 option reference: "
            + _fmt_status(probes.get("massive_option_reference_2016"))
        )
        print("    Massive option flat-file visibility:")
        for item in probes.get("massive_s3", []):
            print(
                f"      {item.get('dataset')} {item.get('year')}: "
                f"{item.get('status')}"
            )

    manifest_path = (
        args.output.resolve()
        if args.output is not None
        else (PROJECT_ROOT / "data/manifests/news_options_source_preflight.json")
    )
    print(f"\n  manifest: {manifest_path}")
    print(
        "  bulk downloads performed: "
        f"{int(report['bulk_downloads_performed'])}"
    )
    print(
        "\nThis preflight performed no bulk downloads. "
        "Existing news/options data from prior acquisition is not re-downloaded."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
