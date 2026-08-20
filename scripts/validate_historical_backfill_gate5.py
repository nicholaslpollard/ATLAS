from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_quality_outliers import (
    AlpacaBackfillGate5Validator,
    AlpacaBackfillQualityOutlierBuilder,
)
from packages.data.alpaca_backfill_validated_evidence import (
    AlpacaBackfillValidatedEvidenceBuilder,
    AlpacaBackfillValidatedEvidenceValidator,
)


def main() -> None:
    settings = load_settings()
    cache = AlpacaBackfillValidatedEvidenceBuilder(settings).run()
    cache_validation = AlpacaBackfillValidatedEvidenceValidator(settings).run()
    if cache_validation.get("pass") is not True:
        raise SystemExit("Historical validated-evidence performance checkpoint: FAIL")

    outlier = AlpacaBackfillQualityOutlierBuilder(settings).run()
    final = AlpacaBackfillGate5Validator(settings).run()

    print("ATLAS Historical Backfill Gate 5 Final Validation")
    print("  performance checkpoint:")
    print(f"    validated-evidence contract:    {cache['contract_version']}")
    print(f"    source fingerprint:             {cache['source_fingerprint']}")
    print(f"    identity-safe rows:             {int(cache['identity_safe_rows']):,}")
    print(f"    trade-backed rows:              {int(cache['trade_backed_rows']):,}")
    print(f"    zero-activity placeholders:     {int(cache['zero_activity_placeholder_rows']):,}")
    print("    cache checks:")
    for name, value in cache_validation["checks"].items():
        print(f"      {name}: {value}")

    print("  raw-return diagnostics:")
    print(f"    contract:                       {outlier['contract_version']}")
    print(f"    policy:                         {outlier['raw_outlier_policy']}")
    print(f"    transition rows:                {int(outlier['transition_rows']):,}")
    print(f"    expected transition rows:       {int(outlier['expected_transition_rows']):,}")
    print(f"    transition accounting exact:    {outlier['transition_accounting_exact']}")
    print(f"    abs return >= 25%:              {int(outlier['absolute_return_ge_25pct']):,}")
    print(f"    abs return >= 50%:              {int(outlier['absolute_return_ge_50pct']):,}")
    print(f"    abs return >= 100%:             {int(outlier['absolute_return_ge_100pct']):,}")
    print(f"    abs return >= 250%:             {int(outlier['absolute_return_ge_250pct']):,}")
    print(f"    abs return >= 500%:             {int(outlier['absolute_return_ge_500pct']):,}")
    print(f"    max absolute return:            {float(outlier['max_absolute_return']):.6f}")
    print(f"    symbols with >=100% return:     {int(outlier['symbols_with_ge_100pct_return']):,}")
    print(f"    sessions with >=100% return:    {int(outlier['sessions_with_ge_100pct_return']):,}")
    print(f"    max >=100% on one session:      {int(outlier['max_ge_100pct_returns_same_session']):,}")
    print(f"    max >=100% session ratio:       {float(outlier['max_ge_100pct_session_ratio']):.6f}")
    print(f"    nonpositive return inputs:      {int(outlier['nonpositive_return_input_rows']):,}")
    print(f"    top outliers:                   {outlier['top_outliers_path']}")
    print(f"    market clusters:                {outlier['market_clusters_path']}")

    print("  Gate 5 checks:")
    for name, value in final["checks"].items():
        print(f"    {name}: {value}")
    if final.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 5 provider completeness / quality: FAIL")
    print("  Historical Backfill Gate 5 provider completeness / quality: PASS")
    print("  Historical Backfill Gate 6 candidate canonical materialization: CURRENT")


if __name__ == "__main__":
    main()
