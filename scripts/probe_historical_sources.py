from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_source_probe import HistoricalSourceAccessProbe


def _print_bar_test(name: str, payload: dict[str, object]) -> None:
    print(
        f"      {name}: status={payload.get('status')} http={payload.get('http_status')} "
        f"bars={payload.get('bar_count', 0)} first={payload.get('first_timestamp')} "
        f"last={payload.get('last_timestamp')}"
    )
    provider_message = payload.get("provider_message")
    if provider_message:
        print(f"        provider_message={provider_message}")


def _print_stooq_test(name: str, payload: dict[str, object]) -> None:
    print(
        f"      {name}: status={payload.get('status')} http={payload.get('http_status')} "
        f"rows={payload.get('row_count', 0)} first={payload.get('first_date')} "
        f"last={payload.get('last_date')}"
    )
    preview = payload.get("response_preview")
    if preview:
        print(f"        response_preview={preview!r}")


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Historical Data Source Access Probe")
    print("  read-only: no provider/canonical history will be modified")
    report = HistoricalSourceAccessProbe(settings).run()
    print(f"  contract:                    {report.contract_version}")
    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print("  Alpaca:")
    for profile, raw in report.alpaca.items():
        payload = dict(raw)
        print(
            f"    profile={profile}: configured={payload.get('configured')} "
            f"status={payload.get('status')} credentials_echoed={payload.get('credentials_echoed')}"
        )
        tests = payload.get("tests")
        if isinstance(tests, dict):
            for name, value in tests.items():
                if isinstance(value, dict):
                    _print_bar_test(name, value)
        corporate = payload.get("corporate_actions")
        if isinstance(corporate, dict):
            print(
                "      corporate_actions: "
                f"status={corporate.get('status')} http={corporate.get('http_status')} "
                f"keys={corporate.get('top_level_keys')}"
            )
            if corporate.get("provider_message"):
                print(f"        provider_message={corporate.get('provider_message')}")

    print("  Stooq:")
    stooq_tests = report.stooq.get("tests")
    if isinstance(stooq_tests, dict):
        for name, value in stooq_tests.items():
            if isinstance(value, dict):
                _print_stooq_test(name, value)

    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
