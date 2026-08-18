from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.features.lake_audit import FeatureLakeAuditor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit ATLAS permanent 1d/4h/1h feature coverage and state lineage."
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--deep-feature-sha",
        action="store_true",
        help="Hash every persisted feature Parquet and compare it to the manifest SHA-256.",
    )
    return parser


def _show_dates(label: str, values: tuple[date, ...]) -> None:
    if not values:
        return
    preview = ", ".join(str(value) for value in values[:10])
    suffix = "" if len(values) <= 10 else f" ... (+{len(values) - 10:,})"
    print(f"    {label}: {preview}{suffix}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.end < args.start:
        raise SystemExit("--end precedes --start")

    settings = load_settings(PROJECT_ROOT)
    audit = FeatureLakeAuditor(settings).audit(
        start=args.start,
        end=args.end,
        deep_feature_sha=args.deep_feature_sha,
    )

    print("ATLAS Permanent Feature Lake Audit")
    print(f"  range:              {audit.start} -> {audit.end}")
    print(f"  expected sessions:  {audit.expected_sessions:,}")
    print(f"  deep feature SHA:   {'enabled' if args.deep_feature_sha else 'disabled'}")
    for item in audit.timeframes:
        print(f"\n  {item.timeframe.value}")
        print(f"    manifests:        {item.manifest_sessions:,}/{item.expected_sessions:,}")
        print(f"    feature rows:     {item.total_rows:,}")
        print(f"    checkpoint as-of: {item.checkpoint_as_of}")
        print(f"    state tail match: {'PASS' if item.checkpoint_matches_tail else 'FAIL'}")
        print(f"    result:           {'PASS' if item.passed else 'FAIL'}")
        _show_dates("missing source", item.missing_sources)
        _show_dates("missing feature", item.missing_features)
        _show_dates("missing manifest", item.missing_manifests)
        _show_dates("invalid manifest", item.invalid_manifests)
        _show_dates("source SHA mismatch", item.source_hash_mismatches)
        _show_dates("feature SHA/path mismatch", item.feature_hash_mismatches)
        _show_dates("state-chain break", item.state_chain_breaks)

    print("\nATLAS combined feature lake result")
    print(f"  total persisted rows: {audit.total_rows:,}")
    print(f"  result:               {'PASS' if audit.passed else 'FAIL'}")
    return 0 if audit.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
