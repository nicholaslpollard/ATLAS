from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.hierarchy_audit import RegimeHierarchyAudit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 9 Gate 13 hierarchy integrity audit.")
    parser.add_argument("--as-of", required=True, help="Finalized/as-of session YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    from datetime import date

    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    report = RegimeHierarchyAudit(load_settings(PROJECT_ROOT, "development")).run(as_of)

    print("ATLAS Phase 9 Gate 13 Regime Hierarchy Integrity Audit")
    print(f"  contract:                       {report.contract_version}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  audit status:                   {report.audit_status}")
    print(f"  hierarchy ready:                {report.hierarchy_ready}")
    print(f"  market snapshot valid:          {report.market_snapshot_valid}")
    print(f"  market state:                   {report.market_state}")
    print(f"  sector proxies expected:        {report.sector_expected_count:,}")
    print(f"  sector proxies present:         {report.sector_present_count:,}")
    print(f"  sector exact set:               {report.sector_exact_set}")
    print(f"  sector effective states:        {report.sector_effective_state_count:,}")
    print(f"  routed expected:                {report.routed_expected_count:,}")
    print(f"  ticker state records:           {report.ticker_record_count:,}")
    print(f"  unique stable identities:       {report.ticker_unique_instrument_count:,}")
    print(f"  unique current tickers:         {report.ticker_unique_current_ticker_count:,}")
    print(f"  exact route/ticker matches:     {report.route_exact_match_count:,}")
    print(f"  missing routed instruments:     {report.missing_routed_count:,}")
    print(f"  extra ticker-state instruments: {report.extra_ticker_state_count:,}")
    print(f"  current ticker mismatches:      {report.current_ticker_mismatch_count:,}")
    print(f"  effective ticker states:        {report.effective_ticker_state_count:,}")
    print(f"  no current ticker state:        {report.no_current_ticker_state_count:,}")
    print(f"  market context attachable:      {report.market_context_attachable_count:,}")
    print(f"  history status:                 {report.history_status_counts}")
    print(f"  persistence status:             {report.persistence_status_counts}")
    print(f"  risk modes:                     {report.risk_mode_counts}")
    print(f"  industry policy:                {report.industry_policy}")
    print(f"  sector assignment policy:       {report.sector_assignment_policy}")
    print(f"  local classification columns:   {report.local_classification_columns}")
    print(f"  classification sample:          {report.classification_sample_count:,}")
    print(f"  exact sample ticker matches:    {report.classification_exact_ticker_match_count:,}")
    print(f"  sample SIC facts:               {report.classification_sic_count:,}")
    print(f"  sample missing SIC:             {report.classification_missing_sic_count:,}")
    print(f"  classification provider errors: {report.classification_provider_error_count:,}")
    print(f"  optional SIC absence allowed:   {report.optional_sic_absence_is_allowed}")
    print(f"  market snapshot SHA-256:        {report.market_snapshot_sha256}")
    print(f"  ticker snapshot SHA-256:        {report.ticker_snapshot_sha256}")
    print(f"  wall time:                      {report.wall_seconds:,.3f}s")
    print(f"  report:                         {Path(report.report_path).resolve()}")
    print(f"  result:                         {'PASS' if report.hierarchy_ready else 'FAIL'}")
    return 0 if report.hierarchy_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
