from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_cross_section_audit import AlpacaCrossSectionSeamAudit


def main() -> int:
    report = AlpacaCrossSectionSeamAudit(load_settings()).run()
    print("ATLAS Alpaca Stratified Liquidity Provider-Seam Audit")
    print("  read-only: no provider/canonical history will be modified")
    print(f"  contract:                    {report.contract_version}")
    print(f"  overlap:                     {report.sample_start}->{report.sample_end}")
    print(f"  sample per liquidity bucket: {report.sample_per_bucket}")
    print(f"  accepted model:              {report.model_id}")
    print(f"  model artifact present:      {report.model_artifact_present}")
    for bucket, payload in report.per_bucket.items():
        s = payload["summary"]
        print(
            f"  {bucket}: sampled={s['sampled_symbols']} usable={s['usable_symbols']} "
            f"matched={s['matched_sessions']} model_rows={s['model_rows']}"
        )
        print(
            "    volume median-of-medians="
            f"{s['median_of_symbol_median_volume_relative_diff']} "
            "nonvolume p95 median="
            f"{s['median_of_symbol_p95_nonvolume_feature_relative_diff']}"
        )
        print(
            "    probability p95 median="
            f"{s['median_of_symbol_p95_probability_diff']} "
            f"max_symbol_p95={s['max_symbol_p95_probability_diff']} "
            f"max_argmax_change={s['max_symbol_argmax_change_fraction']}"
        )
    a = report.aggregate
    print("  aggregate:")
    print(
        f"    sampled={a['sampled_symbols']} usable={a['usable_symbols']} "
        f"matched={a['matched_sessions']} model_rows={a['model_rows']}"
    )
    print(
        f"    volume median-of-medians={a['median_of_symbol_median_volume_relative_diff']} "
        f"nonvolume p95 median={a['median_of_symbol_p95_nonvolume_feature_relative_diff']}"
    )
    print(
        f"    probability p95 median={a['median_of_symbol_p95_probability_diff']} "
        f"max_symbol_p95={a['max_symbol_p95_probability_diff']} "
        f"max_argmax_change={a['max_symbol_argmax_change_fraction']}"
    )
    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
