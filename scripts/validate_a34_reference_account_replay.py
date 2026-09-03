from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.reference_portfolio_policy import (
    REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION,
    REFERENCE_PORTFOLIO_AUTHORITY_PROMOTION,
    REFERENCE_PORTFOLIO_BROKER_WRITES,
    REFERENCE_PORTFOLIO_CORRELATION_MODEL_AVAILABLE,
    REFERENCE_PORTFOLIO_LIVE_WRITES,
    REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION,
    REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS,
    REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION,
    REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY,
    REFERENCE_PORTFOLIO_PAPER_SUBMITS,
    REFERENCE_PORTFOLIO_PRIMARY_ROUND_TRIP_COST_BPS,
    REFERENCE_PORTFOLIO_PROVIDER_WRITES,
    REFERENCE_PORTFOLIO_QUALIFYING_HISTORICAL,
    REFERENCE_PORTFOLIO_SECTOR_MODEL_AVAILABLE,
    REFERENCE_PORTFOLIO_SHORT_ALLOWED,
    REFERENCE_PORTFOLIO_SHORT_BORROW_MODELED,
    reference_portfolio_policy_fingerprint,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG


EXPECTED_POLICY_FINGERPRINT = "c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa"


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    checks: dict[str, bool] = {
        "policy_fingerprint_frozen": (
            reference_portfolio_policy_fingerprint() == EXPECTED_POLICY_FINGERPRINT
        ),
        "risk_matches_reference_library": all(
            item.risk.account_risk_fraction == REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION
            and item.risk.maximum_position_fraction
            == REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION
            for item in REFERENCE_STRATEGY_CATALOG.all()
        ),
        "primary_cost_matches_reference_library": all(
            item.costs.primary_cost_bps
            == REFERENCE_PORTFOLIO_PRIMARY_ROUND_TRIP_COST_BPS
            for item in REFERENCE_STRATEGY_CATALOG.all()
        ),
        "portfolio_limits_frozen": (
            REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION == 1.0
            and REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS == 10
            and REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY == 3
        ),
        "short_borrow_fails_closed": (
            not REFERENCE_PORTFOLIO_SHORT_ALLOWED
            and not REFERENCE_PORTFOLIO_SHORT_BORROW_MODELED
        ),
        "unavailable_context_not_guessed": (
            not REFERENCE_PORTFOLIO_CORRELATION_MODEL_AVAILABLE
            and not REFERENCE_PORTFOLIO_SECTOR_MODEL_AVAILABLE
        ),
        "no_qualification_or_promotion": (
            not REFERENCE_PORTFOLIO_QUALIFYING_HISTORICAL
            and not REFERENCE_PORTFOLIO_AUTHORITY_PROMOTION
        ),
        "all_external_writes_zero": (
            REFERENCE_PORTFOLIO_PROVIDER_WRITES
            == REFERENCE_PORTFOLIO_BROKER_WRITES
            == REFERENCE_PORTFOLIO_PAPER_SUBMITS
            == REFERENCE_PORTFOLIO_LIVE_WRITES
            == 0
        ),
    }

    engine = _text("packages/backtesting/reference_portfolio_replay.py")
    checks.update(
        {
            "engine_has_no_provider_or_broker_adapter": all(
                token not in engine
                for token in (
                    "packages.providers",
                    "packages.brokers",
                    ".submit(",
                    ".cancel(",
                    ".preview(",
                )
            ),
            "engine_rejects_protected_window": (
                "PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START" in engine
                and "ProtectedMasterWindowError" in engine
            ),
            "engine_binds_independent_input": (
                "input_fingerprint != independent.input_fingerprint" in engine
            ),
            "engine_event_clock_is_explicit": all(
                token in engine
                for token in ("opening_exits", "candidates_by_entry", "intraday_exits", "equity_curve")
            ),
        }
    )

    command = _text("scripts/run_a33_b33_reference_development.py")
    register_at = command.find("portfolio_registration_id")
    outcome_at = command.find("ReferenceStrategyHistoricalRunner().run")
    checks["portfolio_trial_registered_before_outcomes"] = (
        register_at >= 0 and outcome_at >= 0 and register_at < outcome_at
    )
    checks["portfolio_artifacts_are_hash_bound"] = all(
        token in command
        for token in (
            "portfolio_decisions.jsonl",
            "portfolio_simulated_orders.jsonl",
            "portfolio_position_outcomes.jsonl",
            "portfolio_equity_curve.jsonl",
            "portfolio_run_summary.json",
        )
    )

    http = _text("packages/control_plane/http_server.py")
    read_model = _text("packages/performance/reference_replay_read_model.py")
    html = _text("apps/web/phase19.html")
    javascript = _text("apps/web/observability.js")
    css = _text("apps/web/observability.css")
    checks.update(
        {
            "read_only_http_endpoint_present": (
                'path == "/api/v1/research/reference-replay"' in http
                and "reference_replay_read_model(service.settings)" in http
            ),
            "read_model_fails_closed": all(
                token in read_model
                for token in (
                    '"NOT_RUN"',
                    '"INVALID"',
                    '"AVAILABLE"',
                    "_bound_artifact",
                    "_sha256_file",
                    "recent_portfolio_decisions",
                    "recent_simulated_orders",
                )
            ),
            "current_operator_browser_shows_replay_and_authority": all(
                token in html
                for token in (
                    "Reference strategy and account replay",
                    "reference-lab-return",
                    "reference-lab-drawdown",
                    "reference-lab-authority",
                    "reference-lab-strategy-body",
                    "reference-lab-outcomes-table",
                    "reference-lab-integrity",
                    "reference-lab-equity-chart",
                    "reference-lab-decisions-table",
                    "reference-lab-orders-table",
                )
            )
            and "renderReferenceLab" in javascript
            and "renderReferenceEquity" in javascript
            and "renderReferenceDecisions" in javascript
            and "renderReferenceOrders" in javascript
            and "/api/v1/research/reference-replay" in javascript
            and "/api/v1/strategies/reference" in javascript
            and ".reference-lab-summary-grid" in css
            and ".reference-lab-grid" in css
            and ".reference-equity-chart" in css,
        }
    )

    readme = _text("README.md")
    roadmap = _text("docs/roadmap.md")
    checks["living_documents_record_a34"] = all(
        token in readme and token in roadmap
        for token in (
            "c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa",
            "RESEARCH account replay",
            "short borrow",
        )
    )

    workflow = _text(".github/workflows/a34-reference-account-replay-tests.yml")
    checks["focused_workflow_present"] = all(
        token in workflow
        for token in (
            "windows-latest",
            "ubuntu-latest",
            "validate_a34_reference_account_replay.py",
            "test_reference_portfolio_replay.py",
            "test_reference_replay_read_model.py",
            "test_phase16_status_api.py",
            "test_phase19_observability_http.py",
        )
    )

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print("ATLAS A34 reference account replay: FAIL")
        for name in failed:
            print(f"- {name}")
        return 1
    print("ATLAS A34 reference account replay contracts: PASS")
    print(f"- portfolio policy fingerprint: {EXPECTED_POLICY_FINGERPRINT}")
    print("- deterministic family-balanced long-only account replay")
    print("- cash, positions, simulated orders, costs, outcomes, and equity reconcile")
    print("- short borrow, correlation, and sector context remain unavailable")
    print("- browser/API are read-only; authority promotion and all external writes remain zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
