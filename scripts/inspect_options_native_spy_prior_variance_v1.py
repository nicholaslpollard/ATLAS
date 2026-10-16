from __future__ import annotations

"""Read-only prior-window dividend sensitivity for the frozen SPY volatility pilot."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_prior_variance_sensitivity_v1 import (
    build_spy_prior_variance_sensitivity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, unqualified SPY prior-variance sensitivity")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY PRIOR VARIANCE SENSITIVITY V1", flush=True)
    print("  Two pinned JSON reports only; ZERO source, provider, broker, options or outcome scans.", flush=True)
    print("  Comparison is conditional, NOT an accepted historical forecast or historical-return adapter.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        report = build_spy_prior_variance_sensitivity(settings)
        numbers = report["conditional_variance"]
        print(f"  prior closes / return intervals: {report['prior_close_count']} / {report['return_count']}", flush=True)
        print(f"  raw-price conditional annual volatility: {numbers['unadjusted_annualized_volatility']}", flush=True)
        print(f"  one-dividend conditional annual volatility: {numbers['one_dividend_annualized_volatility']}", flush=True)
        print("  source integrity verified; historical publication, complete coverage, feature and performance: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_spy_prior_variance_sensitivity_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > 256 * 1024:
                raise ValueError("prior variance sensitivity report exceeded bound")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > 256 * 1024 or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("prior variance sensitivity output conflicts; original retained")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']}; fingerprint: {report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ArithmeticError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original reports preserved; no fallback sources or paid requests.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
