from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.classification_probe import RegimeClassificationProbe


def _pct(value: float) -> str:
    return f"{value * 100.0:6.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe point-in-time Massive SIC coverage for Phase 9 regime classification"
    )
    parser.add_argument("--date", dest="as_of_date", type=date.fromisoformat, required=True)
    parser.add_argument("--sample-size", type=int, default=250)
    args = parser.parse_args()

    report = RegimeClassificationProbe(load_settings(PROJECT_ROOT, "development")).build(
        args.as_of_date,
        sample_size=args.sample_size,
    )

    print("ATLAS Phase 9 Classification Probe")
    print(f"  contract:                  {report.contract_version}")
    print(f"  as-of date:                {report.as_of_date}")
    print(f"  discovery population:      {report.population_count:,}")
    print(f"  requested sample:          {report.requested_sample_size:,}")
    print(f"  sampled:                   {report.sampled_count:,}")
    print(f"  provider responses:        {report.successful_response_count:,}")
    print(f"  exact ticker matches:      {report.exact_ticker_match_count:,}")
    print(f"  SIC code present:          {report.sic_code_count:,}")
    print(f"  SIC description present:   {report.sic_description_count:,}")
    print(f"  missing SIC:               {report.missing_sic_count:,}")
    print(f"  provider errors:           {report.provider_error_count:,}")
    print(f"  SIC coverage/responses:    {_pct(report.sic_coverage_fraction)}")

    print("  by security type:")
    for security_type, counts in report.by_security_type.items():
        print(
            f"    {security_type:<12} sampled={counts['sampled']:>4,} "
            f"ok={counts['successful']:>4,} sic={counts['sic_code']:>4,} "
            f"missing={counts['missing_sic']:>4,} errors={counts['provider_error']:>4,}"
        )

    if report.top_sic_descriptions:
        print("  top SIC descriptions:")
        for item in report.top_sic_descriptions[:10]:
            print(f"    {int(item['count']):>4,}  {item['sic_description']}")

    print(f"  report:                    {report.report_path}")
    if report.successful_response_count <= 0:
        print("  result:                    NO PROVIDER RESPONSES")
        return 2
    print("  result:                    EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
