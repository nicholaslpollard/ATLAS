from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.stooq_bulk_audit import StooqBulkAudit


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Stooq bulk-history access and optionally inspect d_us_txt.zip")
    parser.add_argument("--zip", dest="zip_path", type=Path, default=None, help="Path to manually downloaded d_us_txt.zip")
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT)
    report = StooqBulkAudit(settings, args.zip_path).run()
    print("ATLAS Stooq Bulk Historical Data Probe")
    print("  read-only: no provider/canonical history will be modified")
    print(f"  contract:                    {report.contract_version}")
    print("  direct bulk URL preflight:")
    for item in report.preflight:
        print(
            f"    {item['url']}: status={item['status']} http={item['http_status']} "
            f"zip_signature={item.get('zip_signature')} html_challenge={item.get('html_challenge')} "
            f"content_type={item.get('content_type')} content_length={item.get('content_length')}"
        )
    print(f"  local ZIP:                   {report.local_zip_path}")
    print(f"  local ZIP present:           {report.local_zip_present}")
    print(f"  ZIP valid:                   {report.zip_valid}")
    print(f"  TXT members:                 {report.txt_member_count}")
    if report.selected_symbols:
        print("  selected symbols:")
        for symbol, item in report.selected_symbols.items():
            print(
                f"    {symbol}: member={item.get('member')} rows={item.get('rows')} "
                f"first={item.get('first_date')} last={item.get('last_date')}"
            )
    if not report.local_zip_present:
        print("  note: if direct URLs are challenged, manually download U.S. Daily ASCII d_us_txt.zip from Stooq Historical Data")
        print("        and rerun with: .\\.venv\\Scripts\\python.exe scripts\\probe_stooq_bulk.py --zip <path-to-d_us_txt.zip>")
    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
