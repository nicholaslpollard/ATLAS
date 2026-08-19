from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.alpaca_history_audit import AlpacaHistoryCompatibilityAudit


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Alpaca Historical SIP / Massive Compatibility Audit", flush=True)
    print("  read-only: no provider/canonical history will be modified", flush=True)
    report = AlpacaHistoryCompatibilityAudit(settings).run()

    print(f"  contract:                    {report.contract_version}")
    print(f"  credential profile:          {report.credential_profile_used}")
    print(f"  request semantics:           feed={report.feed} adjustment={report.adjustment} asof={report.asof}")
    print("  depth evidence:")
    for symbol, item in report.depth.items():
        print(
            f"    {symbol}: status={item['status']} http={item['http_status']} rows={item['rows']} "
            f"earliest={item['earliest_session']} latest={item['latest_session']}"
        )

    print("  Massive overlap evidence:")
    for symbol, item in report.ordinary_overlap.items():
        print(
            f"    {symbol}: matched={item['matched_sessions']} alpaca={item['alpaca_rows']} massive={item['massive_rows']} "
            f"close_med={_fmt(item['median_abs_close_relative_diff'])} "
            f"close_p95={_fmt(item['p95_abs_close_relative_diff'])} "
            f"close<=1bp={_fmt(item['close_within_1bp_fraction'])} "
            f"vol_med={_fmt(item['median_abs_volume_relative_diff'])} "
            f"vol_p95={_fmt(item['p95_abs_volume_relative_diff'])}"
        )
        if item["alpaca_only_sessions"] or item["massive_only_sessions"]:
            print(
                f"      session gaps: alpaca_only={item['alpaca_only_sessions']} "
                f"massive_only={item['massive_only_sessions']}"
            )

    print("  split-window evidence:")
    for name, item in report.split_windows.items():
        print(
            f"    {name}: matched={item['matched_sessions']} "
            f"close_p95={_fmt(item['p95_abs_close_relative_diff'])} "
            f"vol_p95={_fmt(item['p95_abs_volume_relative_diff'])}"
        )
        print(f"      alpaca largest close ratio={item['alpaca_largest_adjacent_close_ratio']}")
        print(f"      massive largest close ratio={item['massive_largest_adjacent_close_ratio']}")

    corporate = report.corporate_actions
    print(
        "  corporate actions:           "
        f"status={corporate['status']} http={corporate['http_status']} "
        f"types={corporate['type_counts']} next_page={corporate['next_page_token_present']}"
    )
    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
