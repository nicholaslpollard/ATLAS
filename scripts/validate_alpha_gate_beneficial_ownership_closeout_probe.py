from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_TARGET_HEAD = "067dc13429c22dc4e789959f56644423f0947946"
EXPECTED_PROBE_CONTRACT = (
    "alpha-gate-beneficial-ownership-closeout-probe-v1-persisted-development-negative-no-provider-reads"
)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    module_path = "packages/backtesting/alpha_gate_beneficial_ownership_closeout_probe.py"
    runner_path = "scripts/probe_alpha_gate_beneficial_ownership_closeout_evidence.py"
    workflow_path = ".github/workflows/beneficial-ownership-alpha-gate-tests.yml"
    module = _read(module_path)
    runner = _read(runner_path)
    workflow = _read(workflow_path)
    ast.parse(module, filename=module_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.alpha_gate_beneficial_ownership_closeout_probe import (
        BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        BENEFICIAL_OWNERSHIP_CLOSEOUT_PROBE_CONTRACT,
        BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_OUTCOME_ROWS,
        BENEFICIAL_OWNERSHIP_EXPECTED_PREDICTOR_ROWS,
        BENEFICIAL_OWNERSHIP_EXPECTED_PROTECTED_PREDICTOR_ROWS,
    )

    if BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD != EXPECTED_TARGET_HEAD:
        raise AssertionError("beneficial-ownership accepted development target head drifted")
    if BENEFICIAL_OWNERSHIP_CLOSEOUT_PROBE_CONTRACT != EXPECTED_PROBE_CONTRACT:
        raise AssertionError("beneficial-ownership closeout probe contract drifted")
    if BENEFICIAL_OWNERSHIP_EXPECTED_PREDICTOR_ROWS != 3652:
        raise AssertionError("beneficial-ownership predictor row count drifted")
    if BENEFICIAL_OWNERSHIP_EXPECTED_PROTECTED_PREDICTOR_ROWS != 889:
        raise AssertionError("beneficial-ownership protected predictor count drifted")
    if BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_OUTCOME_ROWS != 2412:
        raise AssertionError("beneficial-ownership development outcome count drifted")

    for token in (
        EXPECTED_TARGET_HEAD,
        EXPECTED_PROBE_CONTRACT,
        "BENEFICIAL_OWNERSHIP_EXPECTED_PREDICTOR_ROWS = 3652",
        "BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_PREDICTOR_ROWS = 2763",
        "BENEFICIAL_OWNERSHIP_EXPECTED_PROTECTED_PREDICTOR_ROWS = 889",
        "BENEFICIAL_OWNERSHIP_EXPECTED_DEVELOPMENT_OUTCOME_ROWS = 2412",
        "BENEFICIAL_OWNERSHIP_EXPECTED_MISSING_STOCK_PATH_ROWS = 306",
        "BENEFICIAL_OWNERSHIP_EXPECTED_SPLIT_CENSORED_ROWS = 46",
        "BENEFICIAL_OWNERSHIP_EXPECTED_PROVIDER_SOURCE_READS = 3133",
        "\"selection_passers_empty\"",
        "\"internal_finalists_empty\"",
        "\"protected_returns_unread\"",
        "\"phase33_authority_false\"",
    ):
        _require(module, token, "closeout probe invariant")

    for forbidden in (
        "read_parquet",
        "connect_utc",
        "MassiveRESTClient",
        "MassiveCIKPITReferenceProvider",
        "SECEDGARArchiveClient",
        "requests.",
        "urllib.",
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(module, forbidden, "provider/performance/trading authority in probe")
        _forbid(runner, forbidden, "provider/performance/trading authority in probe runner")

    _require(runner, "PERSISTED LOCAL ARTIFACTS ONLY", "persisted-evidence boundary")
    _require(runner, "Development/protected outcome recomputation: DISABLED", "no-recompute boundary")
    _require(runner, "Protected returns: FORBIDDEN / UNREAD", "protected boundary")
    _require(workflow, "Validate beneficial-ownership closeout evidence probe contracts", "focused probe validator")
    _require(workflow, "python scripts/validate_alpha_gate_beneficial_ownership_closeout_probe.py", "focused probe validator command")
    _require(workflow, "tests/unit/test_alpha_gate_beneficial_ownership_closeout_probe.py", "focused probe unit test")

    print("ATLAS SEC beneficial-ownership closeout evidence probe contracts: PASS")
    print(f"- accepted development target head: {EXPECTED_TARGET_HEAD}")
    print("- target development negative counts are frozen before closeout pinning")
    print("- probe reads persisted local artifacts only and performs zero provider/outcome recomputation")
    print("- protected returns remain unread; Phase33 authority remains false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
