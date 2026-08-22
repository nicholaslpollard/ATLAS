from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_state_chain import (
    HistoricalBackfillDailyFeatureStateChain,
)


def main() -> None:
    report = HistoricalBackfillDailyFeatureStateChain(load_settings()).run()
    print("ATLAS Historical Backfill Gate 9-C Per-Session Feature State Chain")
    print("  safety: candidate evidence only; production feature lake is read-only")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  Gate 9-C preflight fingerprint:   {report['gate9c_preflight_source_fingerprint']}")
    print(f"  Gate 9-B replay fingerprint:      {report['replay_source_fingerprint']}")
    print(f"  sessions:                         {int(report['sessions']):,}")
    print(f"  first session:                    {report['first_session']}")
    print(f"  last session:                     {report['last_session']}")
    print(f"  rebuilt years:                    {report['rebuilt_years']}")
    print(f"  reused years:                     {report['reused_years']}")
    print("  year checkpoint reconciliation:")
    for row in report["year_reconciliations"]:
        print(
            f"    {int(row['year'])}: sessions={int(row['sessions']):,}, "
            f"match={row['match']}, reused={row['reused']}"
        )
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  chain artifact:                   {report['chain_path']}")
    print(f"  report:                           {report['report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C per-session state chain: FAIL")
    print("  Historical Backfill Gate 9-C per-session state chain: PASS")
    print("  Historical Backfill Gate 9-C production feature write: NOT YET EXECUTED")


if __name__ == "__main__":
    main()
