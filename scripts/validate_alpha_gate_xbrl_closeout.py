from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_TARGET_HEAD = "58e7c9b60ba59d250a7c91e282daefa4aef3c2b9"
EXPECTED_SCIENTIFIC = "2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490"
EXPECTED_IMPLEMENTATION = "3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f"
EXPECTED_CLOSEOUT_CONTRACT = "alpha-gate-xbrl-closeout-v1-development-negative-protected-unread"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    closeout_path = "packages/backtesting/alpha_gate_xbrl_closeout.py"
    runner_path = "scripts/run_alpha_gate_xbrl_closeout.py"
    development_doc_path = "docs/alpha_gate_sec_xbrl_development.md"
    workflow_path = ".github/workflows/xbrl-alpha-gate-tests.yml"

    closeout = _read(closeout_path)
    runner = _read(runner_path)
    development_doc = _read(development_doc_path)
    workflow = _read(workflow_path)
    ast.parse(closeout, filename=closeout_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.alpha_gate_xbrl_closeout import (
        XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        XBRL_CLOSEOUT_CONTRACT,
        XBRLCloseoutError,
        xbrl_closeout_disposition,
    )
    from packages.backtesting.alpha_gate_xbrl_development import (
        XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    )
    from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
        XBRL_SCIENTIFIC_FINGERPRINT,
    )

    if XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD != EXPECTED_TARGET_HEAD:
        raise AssertionError("accepted XBRL target development head drifted")
    if XBRL_SCIENTIFIC_FINGERPRINT != EXPECTED_SCIENTIFIC:
        raise AssertionError("XBRL scientific fingerprint drifted")
    if XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT != EXPECTED_IMPLEMENTATION:
        raise AssertionError("XBRL development implementation fingerprint drifted")
    if XBRL_CLOSEOUT_CONTRACT != EXPECTED_CLOSEOUT_CONTRACT:
        raise AssertionError("XBRL negative closeout contract drifted")

    if xbrl_closeout_disposition(
        status="ACCEPTED_NEGATIVE_DEVELOPMENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("ACCEPTED_NEGATIVE", True):
        raise AssertionError("development-negative closeout semantics drifted")
    if xbrl_closeout_disposition(
        status="ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("ACCEPTED_NEGATIVE", True):
        raise AssertionError("protected-source-negative closeout semantics drifted")
    if xbrl_closeout_disposition(
        status="DEVELOPMENT_PASS_FINALISTS_READY_PROTECTED",
        protected_return_eligible_finalists=["example"],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("PENDING_PROTECTED_CONFIRMATION", False):
        raise AssertionError("protected-eligible candidate would close before confirmation")
    try:
        xbrl_closeout_disposition(
            status="ACCEPTED_NEGATIVE_DEVELOPMENT",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )
    except XBRLCloseoutError:
        pass
    else:
        raise AssertionError("negative closeout accepted consumed protected evidence")

    for token in (
        EXPECTED_TARGET_HEAD,
        EXPECTED_CLOSEOUT_CONTRACT,
        "XBRL_ACCEPTED_PREDICTOR_ROWS = 5536",
        "XBRL_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS = 4157",
        "XBRL_ACCEPTED_PROTECTED_PREDICTOR_ROWS = 1379",
        "XBRL_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS = 3963",
        "XBRL_ACCEPTED_MISSING_STOCK_PATH_ROWS = 123",
        "XBRL_ACCEPTED_SPLIT_CENSORED_ROWS = 71",
        "XBRL_ACCEPTED_PROVIDER_SOURCE_READS = 3415",
        '"selection_passers_empty"',
        '"selection_winners_empty"',
        '"internal_finalists_empty"',
        '"protected_eligible_finalists_empty"',
        '"protected_returns_unread"',
        '"protected_holdout_unconsumed"',
        '"phase33_authority_false"',
    ):
        _require(closeout, token, "negative closeout invariant")

    for forbidden in (
        "read_parquet",
        "connect_utc",
        "MassiveRESTClient",
        "MassiveCIKPITReferenceProvider",
        "SECXBRLCompanyFactsClient",
        "SECXBRLPITMetadataClient",
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(closeout, forbidden, "provider/performance/trading authority in closeout")
        _forbid(runner, forbidden, "provider/performance/trading authority in closeout runner")

    _require(runner, "Protected returns: FORBIDDEN / UNREAD", "runner protected boundary")
    _require(runner, "Provider calls: DISABLED / ZERO", "runner provider boundary")
    _require(runner, "Historical supported alpha", "runner support result")
    _require(runner, "Phase33 authority", "runner downstream authority")
    _require(runner, "materially different alpha mechanism", "runner anti-retuning next action")

    _require(development_doc, "ACCEPTED_NEGATIVE_DEVELOPMENT", "documented target development status")
    _require(development_doc, EXPECTED_TARGET_HEAD, "documented target development head")
    _require(development_doc, "Selection passers: **0**", "documented zero selection passers")
    _require(development_doc, "Internal finalists: **0**", "documented zero finalists")
    _require(development_doc, "Protected return rows read: **0**", "documented protected blindness")
    _require(development_doc, "Protected holdout consumed: **false**", "documented holdout state")

    _require(workflow, "Validate XBRL negative closeout contracts", "focused closeout validator step")
    _require(workflow, "python scripts/validate_alpha_gate_xbrl_closeout.py", "focused closeout validator command")
    _require(workflow, "tests/unit/test_alpha_gate_xbrl_closeout.py", "focused closeout unit test")

    print("ATLAS SEC XBRL negative closeout contracts: PASS")
    print(f"- accepted development target head: {EXPECTED_TARGET_HEAD}")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC}")
    print(f"- development implementation fingerprint: {EXPECTED_IMPLEMENTATION}")
    print("- target result has zero selection passers, zero winners, and zero internal finalists")
    print("- protected returns remain unread and the holdout remains unconsumed")
    print("- closeout uses persisted evidence only; provider/trading authority is absent")
    print("- negative evidence cannot be converted into Phase33 authority or retuned support")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
