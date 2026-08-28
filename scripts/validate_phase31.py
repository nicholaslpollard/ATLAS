from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_SOURCE_MERGE = "bf673ad82886e7172db0d54a33dd9612fa9ea29e"
EXPECTED_ENDPOINT = "/stocks/filings/vX/form-4"
EXPECTED_PLAN = "Stocks Starter"
EXPECTED_WINDOWS = (
    ("research_boundary", "2021-08-16", "2021-08-20"),
    ("mid_history", "2023-08-14", "2023-08-18"),
    ("development_boundary", "2026-05-04", "2026-05-08"),
    ("protected_boundary", "2026-08-07", "2026-08-11"),
)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _assert_parseable(path: str) -> None:
    ast.parse(_read(path), filename=path)


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    python_files = (
        "packages/providers/massive/phase31.py",
        "packages/backtesting/phase31_feasibility.py",
        "scripts/run_phase31_form4_feasibility.py",
    )
    for path in python_files:
        _assert_parseable(path)

    provider = _read("packages/providers/massive/phase31.py")
    feasibility = _read("packages/backtesting/phase31_feasibility.py")
    runner = _read("scripts/run_phase31_form4_feasibility.py")
    phase_doc = _read("docs/phase31_sec_insider_transaction_alpha.md")
    roadmap = _read("docs/roadmap.md")
    status = _read("docs/current_status.md")
    workflow = _read(".github/workflows/atlas-tests.yml")

    _require(provider, f'PHASE31_FORM4_ENDPOINT = "{EXPECTED_ENDPOINT}"', "Form-4 endpoint")
    _require(provider, 'PHASE31_FORM4_FORM_TYPE = "4"', "original Form-4 only")
    _require(provider, 'PHASE31_FORM4_SORT = "filing_date.asc"', "deterministic sort")
    _require(provider, "PHASE31_FORM4_PAGE_LIMIT = 10000", "page limit")
    _require(provider, '"filing_date.gte"', "lower filing-date bound")
    _require(provider, '"filing_date.lte"', "upper filing-date bound")
    _require(provider, '"form_type": PHASE31_FORM4_FORM_TYPE', "form-type query")
    _require(provider, "tuple(sorted(rows, key=_sort_key))", "deterministic provider sort")

    for bad in ("ticker.upper(", "ticker.lower(", ".str.upper(", ".str.lower(", "casefold("):
        _forbid(provider, bad, "ticker normalization")

    _require(feasibility, EXPECTED_SOURCE_MERGE, "Phase30 source merge")
    _require(feasibility, f'PHASE31_DECLARED_MASSIVE_PLAN = "{EXPECTED_PLAN}"', "declared Massive plan")
    _require(
        feasibility,
        'PHASE31_PUBLIC_AVAILABILITY_RULE = "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"',
        "conservative PIT rule",
    )
    _require(feasibility, "PHASE31_ALPHA_HYPOTHESES_FROZEN = False", "hypotheses not frozen")
    _require(feasibility, "PHASE31_TARGET_OUTCOME_READS_ALLOWED = False", "target outcomes forbidden")
    _require(feasibility, "PHASE31_PROTECTED_OUTCOME_READS_ALLOWED = False", "protected outcomes forbidden")
    _require(feasibility, '"target_outcome_rows_read": 0', "zero target outcome reads")
    _require(feasibility, '"protected_candidate_rows_read": 0', "zero protected candidate reads")
    _require(feasibility, '"protected_return_rows_read": 0', "zero protected return reads")

    for label, start, end in EXPECTED_WINDOWS:
        _require(feasibility, f'Phase31ProbeWindow("{label}", "{start}", "{end}")', f"probe {label}")

    for forbidden in (
        "phase26_development",
        "phase27",
        "phase28",
        "phase29",
        "phase30_development",
        "forward_return",
        "directional_return",
        "future_close",
        "future_date",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
    ):
        _forbid(feasibility, forbidden, "outcome/trading authority in feasibility")

    _require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "runner outcome boundary")
    _require(runner, "Broker/order/PAPER/LIVE activity: DISABLED", "runner trading boundary")

    _require(phase_doc, "next XNYS trading session", "conservative next-session explanation")
    _require(phase_doc, "strictly after", "strict later-session timing")
    _require(phase_doc, "transaction_date", "transaction-date warning")
    _require(phase_doc, "early-access/beta", "beta endpoint warning")
    _require(phase_doc, "No Phase31 market outcomes have been read", "no performance read")

    _require(roadmap, "Active Phase31 — SEC Form-4 Insider-Transaction Alpha", "roadmap Phase31 rebaseline")
    _require(roadmap, "Phase32 — Signal-to-Trade Construction", "shifted signal-to-trade phase")
    _require(roadmap, "Phase38 — Controlled LIVE Activation", "shifted LIVE phase")
    _require(status, "Stocks Starter", "subscription status")
    _require(status, "phase-31-sec-insider-transaction-alpha", "active branch status")

    _require(workflow, "Validate Phase 31 Form-4 feasibility contracts", "CI Phase31 validator step")
    _require(workflow, "python scripts/validate_phase31.py", "CI Phase31 validator command")

    print("ATLAS Phase 31 Form-4 feasibility contracts: PASS")
    print("- roadmap rebaselined after Phase30 accepted-negative closeout")
    print("- Form-4 provider path is read-only, original-filing, deterministic, and case-preserving")
    print("- feasibility reads no target/protected market outcomes")
    print("- conservative next-session-after-filing-date chronology is locked pre-performance")
    print("- broker/order/PAPER/LIVE/automatic-failover authority remains disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
