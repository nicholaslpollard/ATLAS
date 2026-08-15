from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_audit import HistoricalLakeAuditor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit ATLAS historical provider/canonical/derived coverage.")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--deep-validate", action="store_true", help="Fully decompress and validate every provider gzip file.")
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def _print_layer(name, item) -> None:
    print(f"{name:18s} {item.present_sessions:5d}/{item.expected_sessions:5d} present  missing={len(item.missing_sessions):5d}  bytes={item.bytes_on_disk:,}")
    invalid = getattr(item, "invalid_sessions", [])
    if invalid:
        print(f"  invalid sessions: {len(invalid)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    auditor = HistoricalLakeAuditor(load_settings(PROJECT_ROOT))
    report = auditor.audit(args.start, args.end, deep_validate=args.deep_validate)
    print("ATLAS Historical Lake Audit")
    print(f"Range: {args.start} -> {args.end}")
    print(f"Exchange sessions: {len(report.exchange_sessions)}")
    _print_layer("provider 1d", report.provider["1d"])
    _print_layer("provider 1m", report.provider["1m"])
    _print_layer("canonical 1d", report.canonical["1d"])
    _print_layer("canonical 1m", report.canonical["1m"])
    for tf in ("15m", "1h", "4h"):
        _print_layer(f"derived {tf}", report.derived[tf])
    print(f"Quarantine sessions: {len(report.quarantine_sessions)}")
    print(f"Quarantined symbols: {len(report.quarantined_symbols)}")
    print(f"Tracked bytes: {report.total_bytes_on_disk:,}")
    if args.json_out:
        auditor.persist(report, args.json_out)
        print(f"JSON report: {args.json_out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
