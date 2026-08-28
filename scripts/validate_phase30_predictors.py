from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_DECISION_BUFFER_MINUTES,
    PHASE30_NEWS_BASELINE_SESSIONS,
    PHASE30_OUTER_PURGE_DATES,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    phase30_policy_fingerprint,
)
from packages.backtesting.phase30_predictors import (
    PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    PHASE30_FORBIDDEN_MARKET_FIELDS,
    PHASE30_PREDICTOR_FIELDS,
    PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION,
    PHASE30_PROTECTED_NEWS_SHOCK_CONTRACT_VERSION,
)


EXPECTED_POLICY_FINGERPRINT = (
    "341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8"
)


def main() -> None:
    predictor_path = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase30_predictors.py"
    )
    predictor_source = predictor_path.read_text(encoding="utf-8")
    predictor_lower = predictor_source.lower()
    runner_source = (
        PROJECT_ROOT / "scripts" / "run_phase30_news_predictors.py"
    ).read_text(encoding="utf-8")
    future_design_path = PROJECT_ROOT / "docs" / "future_news_sentiment_and_option_fair_value.md"
    future_design = (
        future_design_path.read_text(encoding="utf-8")
        if future_design_path.is_file()
        else ""
    )

    forbidden_market_reader_tokens = (
        "from .phase26_observations",
        "from packages.backtesting.phase26_observations",
        "marketdatapaths(",
        "read_parquet(",
        "from .outcomes",
        "from packages.backtesting.outcomes",
        "mloutcomefeasibilityprobe",
    )
    forbidden_network_or_execution_tokens = (
        "massiverestclient(",
        "massivephase30newsclient(",
        "from packages.brokers",
        "import packages.brokers",
        "from packages.execution",
        "import packages.execution",
        ".submit_order(",
        ".place_order(",
        ".cancel_order(",
    )

    checks = {
        "policy_fingerprint_exact": phase30_policy_fingerprint()
        == EXPECTED_POLICY_FINGERPRINT,
        "metadata_only_news_alpha_exact": PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS
        == ("id", "published_utc", "tickers")
        and PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY is False
        and PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY is False,
        "timing_and_baseline_frozen": PHASE30_DECISION_BUFFER_MINUTES == 30
        and PHASE30_NEWS_BASELINE_SESSIONS == 20,
        "outer_purge_exact": PHASE30_OUTER_PURGE_DATES
        == ("2026-05-07", "2026-05-08", "2026-05-11"),
        "predictor_contracts_present": bool(PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION)
        and bool(PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION)
        and bool(PHASE30_PROTECTED_NEWS_SHOCK_CONTRACT_VERSION),
        "predictor_fields_metadata_only": PHASE30_PREDICTOR_FIELDS
        == (
            "contract_version",
            "phase30_policy_fingerprint",
            "ticker",
            "session_date",
            "session_close_utc",
            "decision_cutoff_utc",
            "current_unique_article_count",
            "previous_20_log1p_mean",
            "news_surprise",
        ),
        "forbidden_market_fields_guarded": "d1_return_1"
        in PHASE30_FORBIDDEN_MARKET_FIELDS
        and "forward_return" in PHASE30_FORBIDDEN_MARKET_FIELDS,
        "accepted_market_calendar_reused": (
            "get_market_calendar" in predictor_source
            and ".regular_open_close(" in predictor_source
        ),
        "first_cutoff_at_or_after_publication_rule": "bisect_left(" in predictor_source,
        "exact_zero_fill_baseline": (
            "counts.get((ticker, prior_index), 0)" in predictor_source
            and "math.log1p(current_count) - previous_mean" in predictor_source
        ),
        "ticker_case_not_normalized": all(
            token not in predictor_source
            for token in (
                "ticker.upper(",
                "ticker.lower(",
                "str(ticker).upper(",
                "str(ticker).lower(",
            )
        ),
        "provider_text_not_accessed_for_alpha": all(
            token not in predictor_source
            for token in (
                'raw.get("title")',
                'raw.get("description")',
                'raw.get("insights")',
                'raw["title"]',
                'raw["description"]',
                'raw["insights"]',
            )
        ),
        "predictor_has_no_market_outcome_reader": not any(
            token in predictor_lower for token in forbidden_market_reader_tokens
        ),
        "predictor_has_no_network_or_execution_authority": not any(
            token in predictor_lower for token in forbidden_network_or_execution_tokens
        ),
        "runner_declares_zero_outcomes": "Market outcome reads: ZERO" in runner_source
        and "Protected returns remain forbidden." in runner_source,
        "future_design_is_downstream_only": future_design_path.is_file()
        and "does not alter the frozen Phase30 scientific policy" in future_design
        and "Supporting Evidence" in future_design
        and "Option Fair-Value Engine" in future_design,
    }

    print(f"Phase 30 policy fingerprint: {phase30_policy_fingerprint()}")
    print(f"Phase 30 predictor contract: {PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(
            "Phase 30 predictor-only contract validation failed: " + ", ".join(failed)
        )
    print("Phase 30 predictor-only news-shock contracts: PASS")


if __name__ == "__main__":
    main()
