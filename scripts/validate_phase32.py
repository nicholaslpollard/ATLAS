from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_SOURCE_MERGE = "ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4"
EXPECTED_MASSIVE_ENDPOINT = "/stocks/filings/vX/index"
EXPECTED_FORM = "8-K"
EXPECTED_PLAN = "Stocks Starter"
EXPECTED_PUBLIC_RULE = "FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    paths = (
        "packages/providers/massive/phase32.py",
        "packages/providers/sec_edgar.py",
        "packages/backtesting/phase32_feasibility.py",
        "scripts/run_phase32_8k_feasibility.py",
    )
    sources = {path: read(path) for path in paths}
    for path, source in sources.items():
        ast.parse(source, filename=path)

    massive = sources["packages/providers/massive/phase32.py"]
    sec = sources["packages/providers/sec_edgar.py"]
    feasibility = sources["packages/backtesting/phase32_feasibility.py"]
    runner = sources["scripts/run_phase32_8k_feasibility.py"]
    roadmap = read("docs/roadmap.md")
    status = read("docs/current_status.md")
    phase_doc = read("docs/phase32_sec_8k_material_event_alpha.md")
    incident = read("docs/phase32_sec_edgar_access_incident.md")
    flow = read("docs/phase_flow.md")
    readme = read("README.md")
    workflow = read(".github/workflows/phase32-tests.yml")
    env_example = read(".env.example")

    from packages.backtesting.phase32_feasibility import (
        PHASE32_ALPHA_HYPOTHESES_FROZEN,
        PHASE32_PROBE_WINDOWS,
        PHASE32_PROTECTED_OUTCOME_READS_ALLOWED,
        PHASE32_PUBLIC_AVAILABILITY_RULE,
        PHASE32_SOURCE_PHASE31_MERGE,
        PHASE32_TARGET_OUTCOME_READS_ALLOWED,
        phase32_feasibility_fingerprint,
    )
    from packages.providers.massive.phase32 import (
        PHASE32_SEC_INDEX_ENDPOINT,
        PHASE32_SEC_INDEX_FORM_TYPE,
        PHASE32_SEC_INDEX_PAGE_LIMIT,
        PHASE32_SEC_INDEX_SORT,
    )
    from packages.providers.sec_edgar import (
        SEC_EDGAR_CONTACT_EMAIL_ENV,
        SEC_EDGAR_INDEX_HEADERS_SUFFIX,
        SEC_EDGAR_MAX_REQUESTS_PER_SECOND,
        SEC_EDGAR_USER_AGENT_PREFIX,
        sec_declared_user_agent,
    )

    if PHASE32_SOURCE_PHASE31_MERGE != EXPECTED_SOURCE_MERGE:
        raise AssertionError("Phase32 source merge drifted")
    if PHASE32_SEC_INDEX_ENDPOINT != EXPECTED_MASSIVE_ENDPOINT:
        raise AssertionError("Phase32 Massive endpoint drifted")
    if PHASE32_SEC_INDEX_FORM_TYPE != EXPECTED_FORM:
        raise AssertionError("Phase32 form type drifted")
    if PHASE32_SEC_INDEX_SORT != "filing_date.asc" or PHASE32_SEC_INDEX_PAGE_LIMIT != 10000:
        raise AssertionError("Phase32 deterministic Massive query drifted")
    if len(PHASE32_PROBE_WINDOWS) != 4:
        raise AssertionError("Phase32 probe-window count drifted")
    if PHASE32_PUBLIC_AVAILABILITY_RULE != EXPECTED_PUBLIC_RULE:
        raise AssertionError("Phase32 public-availability rule drifted")
    if PHASE32_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("Phase32 hypotheses were frozen before feasibility")
    if PHASE32_TARGET_OUTCOME_READS_ALLOWED or PHASE32_PROTECTED_OUTCOME_READS_ALLOWED:
        raise AssertionError("Phase32 feasibility may not read market outcomes")
    if SEC_EDGAR_MAX_REQUESTS_PER_SECOND != 1:
        raise AssertionError("Phase32 SEC client must remain at one request/second during feasibility")
    if SEC_EDGAR_INDEX_HEADERS_SUFFIX != "-index-headers.html":
        raise AssertionError("Phase32 SEC index-header artifact drifted")
    if SEC_EDGAR_CONTACT_EMAIL_ENV != "SEC_EDGAR_CONTACT_EMAIL":
        raise AssertionError("Phase32 SEC fair-access contact environment key drifted")
    if "ATLAS" not in SEC_EDGAR_USER_AGENT_PREFIX:
        raise AssertionError("Phase32 SEC User-Agent prefix no longer identifies ATLAS")
    if sec_declared_user_agent("research@example.com") != "ATLAS Research research@example.com":
        raise AssertionError("Phase32 SEC declared User-Agent no longer matches the SEC sample shape")
    fingerprint = phase32_feasibility_fingerprint()
    if len(fingerprint) != 64:
        raise AssertionError("Phase32 feasibility fingerprint is malformed")

    for token in (
        f'PHASE32_SEC_INDEX_ENDPOINT = "{EXPECTED_MASSIVE_ENDPOINT}"',
        f'PHASE32_SEC_INDEX_FORM_TYPE = "{EXPECTED_FORM}"',
        'PHASE32_SEC_INDEX_SORT = "filing_date.asc"',
        "PHASE32_SEC_INDEX_PAGE_LIMIT = 10000",
        '"filing_date.gte"',
        '"filing_date.lte"',
        '"form_type": PHASE32_SEC_INDEX_FORM_TYPE',
        "tuple(sorted(rows, key=_sort_key))",
    ):
        require(massive, token, "Massive 8-K index contract")
    for bad in ("ticker.upper(", "ticker.lower(", ".str.upper(", ".str.lower(", "casefold("):
        forbid(massive, bad, "ticker normalization")

    for token in (
        'SEC_EDGAR_ALLOWED_HOSTS = {"www.sec.gov"}',
        'SEC_EDGAR_ARCHIVES_PREFIX = "/Archives/edgar/"',
        'SEC_EDGAR_INDEX_HEADERS_SUFFIX = "-index-headers.html"',
        'SEC_EDGAR_CONTACT_EMAIL_ENV = "SEC_EDGAR_CONTACT_EMAIL"',
        "SEC_EDGAR_MAX_REQUESTS_PER_SECOND = 1",
        "SEC_EDGAR_MIN_REQUEST_INTERVAL_SECONDS",
        'ZoneInfo("America/New_York")',
        "from html import unescape",
        "_normalize_presentation_fields",
        "<ACCEPTANCE-DATETIME>",
        "ITEM\\s+INFORMATION",
        "ACCESSION\\s+NUMBER",
        "contains_ACCESSION=",
        "header_sha256=",
        "sec_index_headers_url",
        "SEC_EDGAR_INDEX_HEADERS_SUFFIX",
        "_resolve_contact_email",
        "sec_declared_user_agent",
        '"User-Agent": self._user_agent',
        '"Accept-Encoding": "gzip, deflate"',
        '"Host": "www.sec.gov"',
        "_decode_content",
        "does not match the requested accession",
        "ATLAS did not retry the denial",
    ):
        require(sec, token, "SEC EDGAR provenance/fair-access contract")
    forbid(sec, 'f"{cik_path}/{accession_path}/{accession}.txt"', "complete-submission transport")
    forbid(sec, 'SEC_EDGAR_RAW_HEADER_SUFFIX', "raw SGML transport")
    require(env_example, "SEC_EDGAR_CONTACT_EMAIL=", "local SEC fair-access contact configuration")
    if "SEC_EDGAR_CONTACT_EMAIL=\n" not in env_example:
        raise AssertionError(".env.example must keep the SEC contact value blank")

    require(feasibility, EXPECTED_SOURCE_MERGE, "Phase31 accepted-negative merge lineage")
    require(feasibility, f'PHASE32_DECLARED_MASSIVE_PLAN = "{EXPECTED_PLAN}"', "Massive plan")
    require(feasibility, 'PHASE32_ALPHA_HYPOTHESES_FROZEN = False', "hypotheses unfrozen")
    require(feasibility, 'PHASE32_TARGET_OUTCOME_READS_ALLOWED = False', "development outcomes forbidden")
    require(feasibility, 'PHASE32_PROTECTED_OUTCOME_READS_ALLOWED = False', "protected outcomes forbidden")
    require(feasibility, '"target_outcome_rows_read": 0', "zero target outcome reads")
    require(feasibility, '"protected_candidate_rows_read": 0', "zero protected candidate reads")
    require(feasibility, '"protected_return_rows_read": 0', "zero protected return reads")
    require(feasibility, '"phase33_signal_to_trade_entry_satisfied": False', "Phase33 remains blocked")
    require(feasibility, "_sample_rows", "deterministic bounded SEC sample")
    require(feasibility, "acceptance_date_differs_from_filing_date", "filing/acceptance diagnostic")

    for source_name, source in (("feasibility", feasibility), ("Massive adapter", massive), ("SEC adapter", sec)):
        for forbidden in (
            "forward_return",
            "directional_return",
            "future_close",
            "stock_return",
            "spy_return",
            "packages.execution",
            "packages.brokers",
            "Webull",
            "AlpacaTrading",
            ".submit_order(",
            ".place_order(",
        ):
            forbid(source, forbidden, f"outcome/trading authority in {source_name}")

    require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner hypothesis boundary")
    require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "runner outcome boundary")
    require(runner, "Broker/order/PAPER/LIVE activity: DISABLED", "runner trading boundary")
    require(runner, "SEC fair-access identity: ATLAS + local", "runner fair-access declaration")
    require(runner, "filing-index headers", "runner SEC-header source")

    require(roadmap, "Accepted foundation through Phase31", "roadmap accepted foundation")
    require(roadmap, "Active Phase32 — SEC 8-K Material Corporate-Event Alpha", "roadmap active phase")
    require(roadmap, "Phase33 — Signal-to-Trade Construction", "shifted signal-to-trade")
    require(roadmap, "Phase39 — Controlled LIVE Activation", "shifted LIVE phase")
    require(status, "phase-32-sec-8k-material-event-alpha", "active branch status")
    require(status, "five source-format attempts", "current target failure count")
    require(status, "-index-headers.html", "current official SEC index-header source")
    require(status, "Phase31", "Phase31 closeout provenance")
    require(status, "ACCEPTED_NEGATIVE", "Phase31 accepted-negative status")
    require(status, "PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF", "Phase31 independent proof")
    require(status, "2,992,608", "retained Phase31 acquisition provenance")
    require(status, "45,915", "retained Phase31 source-quality provenance")
    require(status, "scripts/run_phase31_form4_acquisition.py", "retained Phase31 acquisition runner")
    require(status, "scripts/run_phase31_form4_source_quality_repair.py", "retained Phase31 repair runner")
    require(phase_doc, EXPECTED_MASSIVE_ENDPOINT, "Phase32 source endpoint")
    require(phase_doc, "official SEC EDGAR", "official SEC source")
    require(phase_doc, "-index-headers.html", "bounded SEC header artifact")
    require(phase_doc, EXPECTED_PUBLIC_RULE, "Phase32 timing rule")
    require(phase_doc, "zero market outcomes", "Phase32 feasibility blindness")
    require(incident, "FIFTH SOURCE-FORMAT FAILURE", "fifth source-format incident provenance")
    require(incident, "d18aa3592f5a3718f91aeee1291e98c8dcf535ec", "fifth failed target head")
    require(incident, "missing ACCESSION NUMBER", "target parser failure provenance")
    require(incident, "HTML-unescape", "entity-aware parser repair provenance")
    require(flow, "predictor-only Form-4 event construction", "retained Phase31 flow provenance")
    require(flow, "Phase32 — SEC 8-K Material Corporate-Event Alpha", "active flow")
    require(readme, "Active Phase32: SEC 8-K Material Corporate-Event Alpha", "README active phase")
    require(readme, "Phase39", "README downstream numbering")
    require(workflow, "Validate Phase 32 SEC 8-K feasibility contracts", "CI Phase32 step")
    require(workflow, "python scripts/validate_phase32.py", "CI Phase32 validator command")
    if not (PROJECT_ROOT / "tests" / "unit" / "test_phase32_feasibility.py").is_file():
        raise AssertionError("Phase32 focused unit tests are missing")

    print("ATLAS Phase 32 SEC 8-K feasibility contracts: PASS")
    print(f"- source Phase31 merge is pinned: {EXPECTED_SOURCE_MERGE}")
    print("- Massive 8-K index discovery and official SEC acceptance/item provenance are read-only")
    print("- exact acceptance timestamps remain SEC-header Eastern wall-clock values")
    print("- SEC transport targets only the bounded listed -index-headers.html artifact")
    print("- SEC requests use the declared fair-access identity shape, gzip/deflate, and one request/second")
    print("- SEC parsing normalizes HTML entities/presentation tags in a separate view while preserving raw evidence")
    print("- parsed accession remains strict and must reconcile exactly to the requested Massive accession")
    print("- SEC HTTP 403 denials remain fail-closed and are not automatically retried")
    print("- hypotheses remain unfrozen and all target/protected market outcomes remain unread")
    print("- Phase33 signal-to-trade and all broker/order/PAPER/LIVE authority remain blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
