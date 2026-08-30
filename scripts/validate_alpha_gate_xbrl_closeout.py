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
EXPECTED_EVIDENCE = "291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91"
EXPECTED_DEVELOPMENT_REPORT_SHA = "50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6"
EXPECTED_PREDICTOR_REPORT_SHA = "246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16"
EXPECTED_PREDICTOR_ROWS_SHA = "9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a"
EXPECTED_OUTCOMES_SHA = "17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55"
EXPECTED_FINALISTS_SHA = "c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f"


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
    closeout_doc_path = "docs/alpha_gate_sec_xbrl_closeout.md"
    status_path = "docs/current_status.md"
    roadmap_path = "docs/roadmap.md"
    flow_path = "docs/phase_flow.md"
    readme_path = "README.md"
    focused_workflow_path = ".github/workflows/xbrl-alpha-gate-tests.yml"
    full_workflow_path = ".github/workflows/atlas-tests.yml"

    closeout = _read(closeout_path)
    runner = _read(runner_path)
    development_doc = _read(development_doc_path)
    closeout_doc = _read(closeout_doc_path)
    status = _read(status_path)
    roadmap = _read(roadmap_path)
    flow = _read(flow_path)
    readme = _read(readme_path)
    focused_workflow = _read(focused_workflow_path)
    full_workflow = _read(full_workflow_path)
    ast.parse(closeout, filename=closeout_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.alpha_gate_xbrl_closeout import (
        XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
        XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
        XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        XBRL_ACCEPTED_EVIDENCE_FINGERPRINT,
        XBRL_ACCEPTED_FINALISTS_SHA256,
        XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256,
        XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256,
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

    exact = {
        "target head": (XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD, EXPECTED_TARGET_HEAD),
        "scientific fingerprint": (XBRL_SCIENTIFIC_FINGERPRINT, EXPECTED_SCIENTIFIC),
        "development implementation fingerprint": (
            XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
            EXPECTED_IMPLEMENTATION,
        ),
        "closeout contract": (XBRL_CLOSEOUT_CONTRACT, EXPECTED_CLOSEOUT_CONTRACT),
        "closeout evidence fingerprint": (XBRL_ACCEPTED_EVIDENCE_FINGERPRINT, EXPECTED_EVIDENCE),
        "development report SHA": (XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256, EXPECTED_DEVELOPMENT_REPORT_SHA),
        "predictor report SHA": (XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256, EXPECTED_PREDICTOR_REPORT_SHA),
        "predictor rows SHA": (XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256, EXPECTED_PREDICTOR_ROWS_SHA),
        "development outcomes SHA": (XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256, EXPECTED_OUTCOMES_SHA),
        "finalists SHA": (XBRL_ACCEPTED_FINALISTS_SHA256, EXPECTED_FINALISTS_SHA),
    }
    for label, (actual, expected) in exact.items():
        if actual != expected:
            raise AssertionError(f"accepted XBRL {label} drifted")

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
        EXPECTED_EVIDENCE,
        EXPECTED_DEVELOPMENT_REPORT_SHA,
        EXPECTED_PREDICTOR_REPORT_SHA,
        EXPECTED_PREDICTOR_ROWS_SHA,
        EXPECTED_OUTCOMES_SHA,
        EXPECTED_FINALISTS_SHA,
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

    _require(runner, "Accepted closeout evidence fingerprint", "runner accepted fingerprint")
    _require(runner, "Protected returns: FORBIDDEN / UNREAD", "runner protected boundary")
    _require(runner, "Provider calls: DISABLED / ZERO", "runner provider boundary")
    _require(runner, "Historical supported alpha", "runner support result")
    _require(runner, "Phase33 authority", "runner downstream authority")
    _require(runner, "materially different alpha mechanism", "runner anti-retuning next action")

    for doc_name, doc in (
        ("development doc", development_doc),
        ("closeout doc", closeout_doc),
        ("status", status),
        ("roadmap", roadmap),
        ("flow", flow),
        ("README", readme),
    ):
        _require(doc, "ACCEPTED_NEGATIVE", f"{doc_name} final disposition")
        _require(doc, EXPECTED_EVIDENCE, f"{doc_name} accepted closeout fingerprint")
        _require(doc, "protected", f"{doc_name} protected boundary")
        _require(doc, "Phase33", f"{doc_name} downstream authority")

    _require(development_doc, "ACCEPTED_NEGATIVE_DEVELOPMENT", "documented target development status")
    _require(development_doc, EXPECTED_TARGET_HEAD, "documented target development head")
    _require(development_doc, "Selection passers: **0**", "documented zero selection passers")
    _require(development_doc, "Internal finalists: **0**", "documented zero finalists")
    _require(development_doc, "Protected return rows read: **0**", "documented protected blindness")
    _require(development_doc, "Protected holdout consumed: **false**", "documented holdout state")

    for accepted_hash in (
        EXPECTED_DEVELOPMENT_REPORT_SHA,
        EXPECTED_PREDICTOR_REPORT_SHA,
        EXPECTED_PREDICTOR_ROWS_SHA,
        EXPECTED_OUTCOMES_SHA,
        EXPECTED_FINALISTS_SHA,
    ):
        _require(closeout_doc, accepted_hash, "closeout immutable artifact SHA")
    _require(closeout_doc, "Historical supported modern alpha remains **0**", "closeout support state")
    _require(closeout_doc, "Phase33 Signal-to-Trade Construction remains blocked", "closeout Phase33 state")
    _require(closeout_doc, "The family is closed", "closeout anti-retuning state")

    _require(status, "Phase32 remains closed", "status retained Phase32 closure")
    _require(roadmap, "materially different point-in-time fundamental-information mechanism", "roadmap Phase32 mechanism handoff")
    _require(
        roadmap,
        "may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result",
        "roadmap Phase32 anti-retuning handoff",
    )
    _require(flow, "Accepted project foundation: **through Phase32**", "flow accepted numbered boundary")
    _require(readme, "Phase32 is `ACCEPTED_NEGATIVE`", "README retained Phase32 state")

    _require(focused_workflow, "Validate XBRL negative closeout contracts", "focused closeout validator step")
    _require(focused_workflow, "python scripts/validate_alpha_gate_xbrl_closeout.py", "focused closeout validator command")
    _require(focused_workflow, "tests/unit/test_alpha_gate_xbrl_closeout.py", "focused closeout unit test")
    _require(full_workflow, "Validate pre-Phase33 SEC XBRL independent negative closeout", "full CI closeout step")
    _require(full_workflow, "python scripts/validate_alpha_gate_xbrl_closeout.py", "full CI closeout command")

    print("ATLAS SEC XBRL negative closeout contracts: PASS")
    print(f"- accepted development target head: {EXPECTED_TARGET_HEAD}")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC}")
    print(f"- development implementation fingerprint: {EXPECTED_IMPLEMENTATION}")
    print(f"- accepted closeout evidence fingerprint: {EXPECTED_EVIDENCE}")
    print("- all five accepted target artifact SHA-256 values are pinned")
    print("- target result has zero selection passers, zero winners, and zero internal finalists")
    print("- protected returns remain unread and the holdout remains unconsumed")
    print("- closeout uses persisted evidence only; provider/trading authority is absent")
    print("- negative evidence cannot be converted into Phase33 authority or retuned support")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
