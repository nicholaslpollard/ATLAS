from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.alpaca_feature_seam_audit import (
    ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION,
    ALPACA_VOLUME_FEATURES,
    AlpacaFeatureSeamAudit,
)


def _fmt(value: object, digits: int = 6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    settings = load_settings(PROJECT_ROOT, "development")
    audit = AlpacaFeatureSeamAudit(settings)

    print("ATLAS Alpaca Feature / Accepted-Model Provider Seam Audit")
    print("  read-only: no provider/canonical history will be modified")
    print("  rebuilding matched Massive and Alpaca raw-SIP feature streams...")
    report = audit.run()

    print(f"  contract:                    {ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION}")
    print(f"  request semantics:           feed={report.feed} adjustment={report.adjustment} asof={report.asof}")
    print(f"  overlap:                     {report.start}->{report.end}")
    print(f"  symbols:                     {report.symbols}")
    print(f"  features:                    {report.feature_count} / volume-dependent={ALPACA_VOLUME_FEATURES}")
    print("  per-symbol evidence:")
    for symbol, item in report.per_symbol.items():
        print(
            f"    {symbol}: matched={item['matched_sessions']} complete={item['complete_feature_rows']} "
            f"complete_range={item['complete_start']}->{item['complete_end']} "
            f"nonvolume_max_abs_diff={_fmt(item['nonvolume_feature_max_abs_diff'])}"
        )
        for name, metrics in item["volume_feature_differences"].items():
            print(
                f"      {name}: rel_med={_fmt(metrics['median_abs_relative_diff'])} "
                f"rel_p95={_fmt(metrics['p95_abs_relative_diff'])} corr={_fmt(metrics['correlation'])}"
            )

    print("  aggregate volume-feature evidence:")
    for name in ALPACA_VOLUME_FEATURES:
        metrics = report.aggregate_feature_differences.get(name, {})
        print(
            f"    {name}: rows={metrics.get('rows', 0)} "
            f"rel_med={_fmt(metrics.get('median_abs_relative_diff'))} "
            f"rel_p95={_fmt(metrics.get('p95_abs_relative_diff'))} "
            f"corr={_fmt(metrics.get('correlation'))}"
        )

    sensitivity = report.model_probability_sensitivity
    print(f"  accepted model:              {report.model_id}")
    print(f"  model artifact present:      {report.model_artifact_present}")
    print("  model probability sensitivity:")
    if sensitivity.get("status"):
        print(f"    status={sensitivity['status']} rows={sensitivity.get('rows', 0)}")
    else:
        print(f"    rows={sensitivity['rows']}")
        print(f"    mean_abs_probability_diff={_fmt(sensitivity['mean_abs_probability_diff'], 8)}")
        print(f"    median_row_max_diff={_fmt(sensitivity['median_row_max_probability_diff'], 8)}")
        print(f"    p95_row_max_diff={_fmt(sensitivity['p95_row_max_probability_diff'], 8)}")
        print(f"    max_row_diff={_fmt(sensitivity['max_row_probability_diff'], 8)}")
        print(f"    <=1bp fraction={_fmt(sensitivity['rows_with_max_diff_le_1bp_fraction'])}")
        print(f"    <=10bp fraction={_fmt(sensitivity['rows_with_max_diff_le_10bp_fraction'])}")
        print(f"    <=100bp fraction={_fmt(sensitivity['rows_with_max_diff_le_100bp_fraction'])}")
        print(f"    argmax change fraction={_fmt(sensitivity['argmax_change_fraction'])}")

    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
