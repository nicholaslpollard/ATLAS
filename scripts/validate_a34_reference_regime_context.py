from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.reference_lake_adapter import (
    REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION,
)
from packages.backtesting.reference_regime_context import (
    REFERENCE_REGIME_CONTEXT_BROKER_WRITES,
    REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION,
    REFERENCE_REGIME_CONTEXT_LIVE_WRITES,
    REFERENCE_REGIME_CONTEXT_PAPER_SUBMITS,
    REFERENCE_REGIME_CONTEXT_PROTECTED_RETURN_READS,
    REFERENCE_REGIME_CONTEXT_PROVIDER_WRITES,
)


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    context = _text("packages/backtesting/reference_regime_context.py")
    runner = _text("packages/backtesting/reference_strategy_runner.py")
    command = _text("scripts/run_a33_b33_reference_development.py")
    workflow = _text(".github/workflows/a34-reference-account-replay-tests.yml")
    readme = _text("README.md")
    roadmap = _text("docs/roadmap.md")

    attach_at = command.find("ReferenceRegimeContextAdapter(settings).attach")
    strategy_registration_at = command.find("registration_id =")
    portfolio_registration_at = command.find("portfolio_registration_id =")
    outcome_at = command.find("ReferenceStrategyHistoricalRunner().run")
    checks: dict[str, bool] = {
        "close_availability_contract_frozen": (
            REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION
            == "reference-signal-availability-v1-xnys-regular-close-next-open"
        ),
        "regime_context_contract_frozen": (
            REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION
            == "reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only"
        ),
        "all_external_writes_zero": (
            REFERENCE_REGIME_CONTEXT_PROTECTED_RETURN_READS
            == REFERENCE_REGIME_CONTEXT_PROVIDER_WRITES
            == REFERENCE_REGIME_CONTEXT_BROKER_WRITES
            == REFERENCE_REGIME_CONTEXT_PAPER_SUBMITS
            == REFERENCE_REGIME_CONTEXT_LIVE_WRITES
            == 0
        ),
        "context_is_read_only": all(
            token not in context
            for token in (
                "packages.providers",
                "packages.brokers",
                ".build(",
                ".write_text(",
                "COPY (",
                ".submit(",
                ".cancel(",
            )
        ),
        "exact_asof_and_hash_checks_present": all(
            token in context
            for token in (
                '"as_of_date": end_date.isoformat()',
                'manifest.get("snapshot_sha256")',
                'market_entry.get("sha256")',
                "bounds[1] != end_date",
                '"future_regime_rows_read": 0',
            )
        ),
        "unavailable_context_not_guessed": all(
            token in context
            for token in (
                'enriched["sector_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT',
                'enriched["ticker_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT',
                "NO_ACCEPTED_PIT_INSTRUMENT_TO_SECTOR_MAPPING",
            )
        ),
        "runner_uses_close_availability": (
            'signal["signal_available_at_utc"].to_pydatetime()' in runner
            and "signal_available <= bar_timestamps" in runner
        ),
        "context_precedes_registration_and_outcomes": (
            attach_at >= 0
            and strategy_registration_at > attach_at
            and portfolio_registration_at > strategy_registration_at
            and outcome_at > portfolio_registration_at
        ),
        "context_frame_bound_and_replayed": all(
            token in command
            for token in (
                "reference_input_fingerprint(regime_context.bars)",
                "ReferenceStrategyHistoricalRunner().run(regime_context.bars)",
                "ReferenceAccountPortfolioReplay().run(regime_context.bars, run)",
                "regime_context_report.json",
                "regime_source_fingerprint",
            )
        ),
        "living_documents_record_contracts": all(
            token in readme and token in roadmap
            for token in (
                REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION,
                REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION,
                "same-session finalized market regime",
                "ticker and sector",
            )
        ),
        "focused_cross_platform_workflow": all(
            token in workflow
            for token in (
                "windows-latest",
                "ubuntu-latest",
                "validate_a34_reference_regime_context.py",
                "test_reference_regime_context.py",
                "test_reference_lake_adapter.py",
                "test_reference_strategy_runner.py",
            )
        ),
    }

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print("ATLAS A34 PIT regime context: FAIL")
        for name in failed:
            print(f"- {name}")
        return 1
    print("ATLAS A34 PIT regime context contracts: PASS")
    print(f"- close availability: {REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION}")
    print(f"- regime context: {REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION}")
    print("- exact-as-of hash-bound same-close market state; no future rows")
    print("- ticker and sector context remain UNAVAILABLE; no labels are inferred")
    print("- protected returns and provider/broker/PAPER/LIVE writes remain zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
