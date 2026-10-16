from __future__ import annotations

"""Capture original SPDR issuer XLSX and inspect SPY rows, without admitting features."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text, unique_temp_path, replace_with_retry
from packages.core.settings import load_settings
from packages.data.options_native_spy_issuer_distributions_receipt_v1 import (
    build_official_issuer_xlsx_receipt,
    download_official_issuer_xlsx,
    read_local_issuer_xlsx,
)

MAX_REPORT = 256 * 1024


def _write_original_immutable(path: Path, raw: bytes, sha256: str) -> None:
    if path.is_symlink():
        raise ValueError("issuer original raw destination is symlink")
    if path.exists():
        if path.stat().st_size != len(raw) or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError("original issuer workbook path has conflicting bytes")
        return
    tmp = unique_temp_path(path)
    try:
        with tmp.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Check for a concurrently written destination rather than rewriting.
        if path.exists():
            raise ValueError("concurrent issuer source receipt exists; original preserved")
        replace_with_retry(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pin official SPDR historical-distributions XLSX")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--download", action="store_true", help="Exactly one free official State Street HTTPS GET")
    source.add_argument("--local-xlsx", type=Path, help="Previously downloaded unchanged official US issuer XLSX")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY US ISSUER DISTRIBUTION RECEIPT V1", flush=True)
    print("  One original U.S. State Street SPDR historical-distributions XLSX; bound to accepted 411-week SPY diagnostic.", flush=True)
    print("  No price/action-ledger/option/broker/market-outcome scans or paid data calls.", flush=True)
    print("  Workbook rows and publication clock NOT yet qualified as economic history or predictor inputs.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        method = "EXPLICIT_ONE_GET" if args.download else "EXPLICIT_LOCAL_FILE"
        raw = download_official_issuer_xlsx() if args.download else read_local_issuer_xlsx(args.local_xlsx)
        report = build_official_issuer_xlsx_receipt(settings, raw, acquisition_method=method)
        print(f"  original issuer ZIP bytes: {report['original_xlsx_bytes']}", flush=True)
        print(f"  original issuer SHA-256: {report['original_xlsx_sha256']}", flush=True)
        print(f"  worksheets scanned: {len(report['worksheet_scan_summary'])}", flush=True)
        for sheet in report["worksheet_scan_summary"]:
            print(f"    {sheet['sheet_member']}: {sheet['rows_inspected']} total rows, {sheet['spy_identity_matching_rows']} SPY identity rows", flush=True)
        print(f"  raw SPY-identity rows matched: {report['spy_identity_matching_rows']}", flush=True)
        print(f"  SPY-identity sample rows saved: {report['candidate_rows_captured']}", flush=True)
        print("  All feature/source completeness/publication/trade authority: UNQUALIFIED", flush=True)
        if args.save_report:
            directory = settings.resolved_path("data/research/options_native_spy_issuer_distributions_receipt_v1")
            original = directory / "raw" / (report["original_xlsx_sha256"] + ".xlsx")
            report_path = directory / (report["report_fingerprint"][:16] + ".json")
            body = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if len(body.encode("utf-8")) > MAX_REPORT:
                raise ValueError("issuer row discovery JSON exceeds bound")
            if report_path.is_symlink() or (report_path.exists() and (
                report_path.stat().st_size > MAX_REPORT or report_path.read_text(encoding="utf-8") != body
            )):
                raise ValueError("issuer receipt output collides with retained original")
            _write_original_immutable(original, raw, report["original_xlsx_sha256"])
            if not report_path.exists():
                atomic_write_text(report_path, body, fsync=True)
            print(f"  original raw source saved: {original}", flush=True)
            print(f"  saved report: {report_path}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, ArithmeticError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  No paid fallback, no vendor retries; original accepted SPY research untouched.", flush=True)
        print("  If official download is blocked, download the XLSX in your browser and rerun with --local-xlsx PATH.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
