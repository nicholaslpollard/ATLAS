from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_pit_identity_repair import (
    XBRL_PIT_IDENTITY_REPAIR_CONTRACT,
    XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT,
    xbrl_pit_identity_repair_fingerprint,
)


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise SystemExit(f"XBRL PIT identity repair validation failed: missing {label}: {token}")


def _forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise SystemExit(f"XBRL PIT identity repair validation failed: forbidden {label}: {token}")


def main() -> int:
    if xbrl_pit_identity_repair_fingerprint() != XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT:
        raise SystemExit("XBRL PIT identity repair validation failed: frozen fingerprint drifted")

    repair = _read("packages/backtesting/alpha_gate_xbrl_pit_identity_repair.py")
    provider = _read("packages/providers/massive/xbrl_pit.py")
    runner = _read("scripts/run_alpha_gate_xbrl_pit_identity_repair.py")
    tests = _read("tests/unit/test_alpha_gate_xbrl_pit_identity_repair.py")
    doc = _read("docs/alpha_gate_sec_xbrl_pit_identity_repair.md")

    for path, text in (
        ("packages/backtesting/alpha_gate_xbrl_pit_identity_repair.py", repair),
        ("packages/providers/massive/xbrl_pit.py", provider),
        ("scripts/run_alpha_gate_xbrl_pit_identity_repair.py", runner),
        ("tests/unit/test_alpha_gate_xbrl_pit_identity_repair.py", tests),
    ):
        ast.parse(text, filename=path)

    for text, label in ((repair, "repair module"), (doc, "repair doc")):
        _require(text, XBRL_PIT_IDENTITY_REPAIR_CONTRACT, f"{label} contract")
        _require(text, XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT, f"{label} fingerprint")
        _require(text, "139", f"{label} preserved v1 unambiguous count")
        _require(text, "28", f"{label} preserved v1 issuer count")
        _require(text, "MASSIVE_HISTORICAL_DATE_ACTIVE_FALSE_AND_NON_COMMON_TYPES_EXPANDED_NONTRADABLE_UNIVERSE", f"{label} root cause")

    for token in (
        '"audit_issuer_sample_size": 40',
        '"companyfacts_success": 40',
        '"selected_original_filings": 200',
        '"sec_metadata_reconciled": 198',
        '"acceptance_decisions": 198',
        '"unambiguous_identity_mappings": 139',
        '"issuers_with_3_unambiguous_mappings": 28',
        '"same_accession_context_conflicts": 0',
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"provider_reads_performed": 0',
        '"provider_writes_performed": 0',
        '"broker_reads_performed": 0',
        '"broker_writes_performed": 0',
        '"order_writes_performed": 0',
        '"paper_submits_performed": 0',
        '"live_writes_performed": 0',
        '"automation_writes_performed": 0',
        "EXACT_CIK_DATE_ACTIVE_COMMON_STOCK_ONLY_STRONG_OR_MEDIUM_EXACTLY_ONE_UNIQUE_INSTRUMENT",
    ):
        _require(repair, token, "repair invariant")

    _require(provider, "def tradable_common_stock_snapshot", "explicit corrected provider seam")
    _require(provider, "include_inactive=False", "historical active-only query")
    _require(provider, 'security_type="CS"', "common-stock type query")
    _require(provider, 'params["type"] = security_type', "Massive type filter wiring")

    for forbidden in (
        "packages.data.market",
        "packages.execution",
        "packages.brokers",
        "packages.portfolio",
        "read_parquet",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(repair, forbidden, "market outcome/trading dependency")

    _require(runner, "Same 40 issuers, same accessions, same SEC chronology, same numeric gates", "runner no-retuning declaration")
    _require(runner, "no provider calls are performed", "runner local-cache replay declaration")
    _require(runner, "Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD", "runner blindness declaration")
    _forbid(runner, "argparse", "operator scope override")

    _require(tests, "test_identity_repair_fingerprint_is_frozen", "repair fingerprint test")
    _require(tests, "test_massive_tradable_common_stock_snapshot_uses_active_true_and_cs", "provider semantics test")
    _require(tests, "test_repair_replays_existing_cache_and_excludes_inactive_and_non_common", "replay regression test")

    _require(doc, "The v1 failure is not rewritten or converted to PASS.", "preserved failure statement")
    _require(doc, "No threshold is lowered, no failed issuer is replaced", "anti-workaround statement")

    print("ATLAS XBRL PIT targeted identity-semantics repair contracts: PASS")
    print(f"- repair fingerprint: {XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT}")
    print("- v1 AUDIT_FAIL remains preserved at 139 mappings / 28 issuers")
    print("- corrected PIT common-equity identity is active=true + type=CS on the exact historical date")
    print("- same source population and numeric gates are retained; no market outcomes are read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
