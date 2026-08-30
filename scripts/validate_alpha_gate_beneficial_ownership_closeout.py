from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_TARGET_HEAD = "067dc13429c22dc4e789959f56644423f0947946"
EXPECTED_SCIENTIFIC = "4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c"
EXPECTED_IMPLEMENTATION = "0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d"
EXPECTED_TRANSPORT = "a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb"
EXPECTED_CLOSEOUT_CONTRACT = "alpha-gate-beneficial-ownership-closeout-v1-development-negative-protected-unread"
EXPECTED_EVIDENCE = "c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8"
EXPECTED_DEVELOPMENT_REPORT_SHA = "3cfecc2841e71172d2f4575ec6e0ef4dfe3d08d36fd3a95c6237bffb33601e30"
EXPECTED_PREDICTOR_REPORT_SHA = "28997b63b978d4ce44f9719b909075b6be38d50109633547db96881f84b2850b"
EXPECTED_PREDICTOR_ROWS_SHA = "310c7b8edfd5324e57b888734febe9407decc4fb1f042c67a6de07d3a468a466"
EXPECTED_OUTCOMES_SHA = "4c038c5f6578dc9ef946a3485b1584514dbc893b9da976522ed0373c0715b679"
EXPECTED_FINALISTS_SHA = "d0cca3cbe1be332d010b7689b735244d40e760fa2f067e8c9fe1c47ce7b4fbca"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    closeout_path = "packages/backtesting/alpha_gate_beneficial_ownership_closeout.py"
    runner_path = "scripts/run_alpha_gate_beneficial_ownership_closeout.py"
    development_doc_path = "docs/alpha_gate_sec_beneficial_ownership_development.md"
    closeout_doc_path = "docs/alpha_gate_sec_beneficial_ownership_closeout.md"
    status_path = "docs/current_status.md"
    roadmap_path = "docs/roadmap.md"
    flow_path = "docs/phase_flow.md"
    readme_path = "README.md"
    focused_workflow_path = ".github/workflows/beneficial-ownership-alpha-gate-tests.yml"
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

    from packages.backtesting.alpha_gate_beneficial_ownership_closeout import (
        BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
        BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
        BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT,
        BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256,
        BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256,
        BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256,
        BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT,
        BeneficialOwnershipCloseoutError,
        beneficial_ownership_closeout_disposition,
    )
    from packages.backtesting.alpha_gate_beneficial_ownership_development import (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    )
    from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
        BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
    )
    from packages.backtesting.alpha_gate_beneficial_ownership_transport_repair import (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT,
    )

    exact = {
        "target head": (BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD, EXPECTED_TARGET_HEAD),
        "scientific fingerprint": (BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT, EXPECTED_SCIENTIFIC),
        "development implementation fingerprint": (BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT, EXPECTED_IMPLEMENTATION),
        "development transport fingerprint": (BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT, EXPECTED_TRANSPORT),
        "closeout contract": (BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT, EXPECTED_CLOSEOUT_CONTRACT),
        "closeout evidence fingerprint": (BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT, EXPECTED_EVIDENCE),
        "development report SHA": (BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256, EXPECTED_DEVELOPMENT_REPORT_SHA),
        "predictor report SHA": (BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256, EXPECTED_PREDICTOR_REPORT_SHA),
        "predictor rows SHA": (BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256, EXPECTED_PREDICTOR_ROWS_SHA),
        "development outcomes SHA": (BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256, EXPECTED_OUTCOMES_SHA),
        "finalists SHA": (BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256, EXPECTED_FINALISTS_SHA),
    }
    for label, (actual, expected) in exact.items():
        if actual != expected:
            raise AssertionError(f"accepted beneficial-ownership {label} drifted")

    if beneficial_ownership_closeout_disposition(
        status="ACCEPTED_NEGATIVE_DEVELOPMENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("ACCEPTED_NEGATIVE", True):
        raise AssertionError("development-negative closeout semantics drifted")
    if beneficial_ownership_closeout_disposition(
        status="ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
        protected_return_eligible_finalists=[],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("ACCEPTED_NEGATIVE", True):
        raise AssertionError("protected-source-negative closeout semantics drifted")
    if beneficial_ownership_closeout_disposition(
        status="DEVELOPMENT_PASS_FINALIST_READY_PROTECTED",
        protected_return_eligible_finalists=["example"],
        protected_return_rows_read=0,
        protected_holdout_consumed=False,
    ) != ("PENDING_PROTECTED_CONFIRMATION", False):
        raise AssertionError("protected-eligible candidate would close before confirmation")
    try:
        beneficial_ownership_closeout_disposition(
            status="ACCEPTED_NEGATIVE_DEVELOPMENT",
            protected_return_eligible_finalists=[],
            protected_return_rows_read=1,
            protected_holdout_consumed=True,
        )
    except BeneficialOwnershipCloseoutError:
        pass
    else:
        raise AssertionError("negative closeout accepted consumed protected evidence")

    for token in (
        EXPECTED_TARGET_HEAD,
        EXPECTED_EVIDENCE,
        EXPECTED_DEVELOPMENT_REPORT_SHA,
        EXPECTED_PREDICTOR_REPORT_SHA,
        EXPECTED_PREDICTOR_ROWS_SHA,
        EXPECTED_OUTCOMES_SHA,
        EXPECTED_FINALISTS_SHA,
        "BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS = 3652",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS = 2763",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_PROTECTED_PREDICTOR_ROWS = 889",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS = 2412",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_MISSING_STOCK_PATH_ROWS = 306",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_SPLIT_CENSORED_ROWS = 46",
        "BENEFICIAL_OWNERSHIP_ACCEPTED_PROVIDER_SOURCE_READS = 3133",
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
        "SECEDGARArchiveClient",
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
        _require(doc, EXPECTED_EVIDENCE, f"{doc_name} accepted evidence fingerprint")
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

    _require(status, "Historical supported alpha remains 0", "status support state")
    _require(status, "Phase33 remains blocked", "status Phase33 state")
    _require(status, "Beneficial-ownership final scientific disposition: `ACCEPTED_NEGATIVE`", "status beneficial closeout state")
    _require(roadmap, "## 7. Completed Pre-Phase33 SEC Schedule 13D/13G beneficial ownership — `ACCEPTED_NEGATIVE`", "roadmap beneficial closeout heading")
    _require(roadmap, "Historical supported alpha remains **zero**", "roadmap retained support state")
    _require(flow, "Accepted project foundation: **through Phase32**", "flow accepted numbered boundary")
    _require(flow, "The beneficial-ownership family is closed `ACCEPTED_NEGATIVE`", "flow beneficial closeout state")
    _require(readme, "Phase32 is `ACCEPTED_NEGATIVE`", "README retained Phase32 state")
    _require(readme, "Historical supported modern alpha remains **0**", "README support state")

    _require(focused_workflow, "Validate beneficial-ownership independent negative closeout", "focused closeout validator step")
    _require(focused_workflow, "python scripts/validate_alpha_gate_beneficial_ownership_closeout.py", "focused closeout validator command")
    _require(focused_workflow, "tests/unit/test_alpha_gate_beneficial_ownership_closeout.py", "focused closeout unit test")
    _require(full_workflow, "Validate pre-Phase33 SEC beneficial-ownership independent negative closeout", "full CI closeout step")
    _require(full_workflow, "python scripts/validate_alpha_gate_beneficial_ownership_closeout.py", "full CI closeout command")

    print("ATLAS SEC beneficial-ownership negative closeout contracts: PASS")
    print(f"- accepted development target head: {EXPECTED_TARGET_HEAD}")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC}")
    print(f"- accepted closeout evidence fingerprint: {EXPECTED_EVIDENCE}")
    print("- all five accepted target artifact SHA-256 values are pinned")
    print("- target result has zero selection passers, zero winners, and zero internal finalists")
    print("- protected returns remain unread and the holdout remains unconsumed")
    print("- closeout uses persisted evidence only; provider/trading authority is absent")
    print("- living docs are synchronized to the accepted-negative disposition")
    print("- negative evidence cannot be converted into Phase33 authority or retuned support")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
