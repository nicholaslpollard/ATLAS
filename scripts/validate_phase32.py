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
EXPECTED_CONTRACT_VERSION = "phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes"


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
        PHASE32_FEASIBILITY_CONTRACT_VERSION,
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
        SEC_EDGAR_ALLOWED_HOSTS,
        SEC_EDGAR_CONTACT_EMAIL_ENV,
        SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
        SEC_EDGAR_MAX_REQUESTS_PER_SECOND,
        SEC_EDGAR_SUBMISSIONS_PREFIX,
        SEC_EDGAR_USER_AGENT_PREFIX,
        sec_company_submissions_url,
        sec_declared_user_agent,
    )

    if PHASE32_SOURCE_PHASE31_MERGE != EXPECTED_SOURCE_MERGE:
        raise AssertionError("Phase32 source merge drifted")
    if PHASE32_FEASIBILITY_CONTRACT_VERSION != EXPECTED_CONTRACT_VERSION:
        raise AssertionError("Phase32 feasibility contract version drifted")
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
    if SEC_EDGAR_ALLOWED_HOSTS != {"data.sec.gov"}:
        raise AssertionError("Phase32 SEC host drifted")
    if SEC_EDGAR_SUBMISSIONS_PREFIX != "/submissions/":
        raise AssertionError("Phase32 SEC submissions prefix drifted")
    if SEC_EDGAR_MAX_REQUESTS_PER_SECOND != 1:
        raise AssertionError("Phase32 SEC client must remain at one request/second during feasibility")
    if SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP != 2:
        raise AssertionError("Phase32 SEC archive shard bound drifted")
    if SEC_EDGAR_CONTACT_EMAIL_ENV != "SEC_EDGAR_CONTACT_EMAIL":
        raise AssertionError("Phase32 SEC fair-access contact environment key drifted")
    if "ATLAS" not in SEC_EDGAR_USER_AGENT_PREFIX:
        raise AssertionError("Phase32 SEC User-Agent prefix no longer identifies ATLAS")
    if sec_declared_user_agent("research@example.com") != "ATLAS Research research@example.com":
        raise AssertionError("Phase32 SEC declared User-Agent shape drifted")
    if sec_company_submissions_url(cik="4904") != "https://data.sec.gov/submissions/CIK0000004904.json":
        raise AssertionError("Phase32 SEC submissions URL shape drifted")
    if len(phase32_feasibility_fingerprint()) != 64:
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
        'SEC_EDGAR_ALLOWED_HOSTS = {"data.sec.gov"}',
        'SEC_EDGAR_SUBMISSIONS_PREFIX = "/submissions/"',
        'SEC_EDGAR_CONTACT_EMAIL_ENV = "SEC_EDGAR_CONTACT_EMAIL"',
        "SEC_EDGAR_MAX_REQUESTS_PER_SECOND = 1",
        "SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP = 2",
        'ZoneInfo("America/New_York")',
        "acceptanceDateTime",
        "accessionNumber",
        "filingDate",
        '"items"',
        "sec_company_submissions_url",
        "sec_submission_shard_url",
        "_find_accession",
        "_split_items",
        '"User-Agent": self._user_agent',
        '"Accept": "application/json"',
        '"Accept-Encoding": "gzip, deflate"',
        '"Host": "data.sec.gov"',
        "ATLAS did not retry the denial",
        "not original 8-K",
    ):
        require(sec, token, "SEC submissions provenance/fair-access contract")
    for forbidden in (
        "www.sec.gov/Archives/edgar/data",
        "-index-headers.html",
        ".hdr.sgml",
    ):
        forbid(sec, forbidden, "retired SEC archive presentation transport")
    require(env_example, "SEC_EDGAR_CONTACT_EMAIL=", "local SEC fair-access contact configuration")

    require(feasibility, EXPECTED_CONTRACT_VERSION, "Phase32 v2 feasibility contract")
    require(feasibility, EXPECTED_SOURCE_MERGE, "Phase31 accepted-negative merge lineage")
    require(feasibility, f'PHASE32_DECLARED_MASSIVE_PLAN = "{EXPECTED_PLAN}"', "Massive plan")
    require(feasibility, '"sec_source": "SECEDGARClient:data.sec.gov/submissions"', "SEC source fingerprint")
    require(feasibility, '/ "v2"', "v2 immutable evidence namespace")
    require(feasibility, 'PHASE32_ALPHA_HYPOTHESES_FROZEN = False', "hypotheses unfrozen")
    require(feasibility, 'PHASE32_TARGET_OUTCOME_READS_ALLOWED = False', "development outcomes forbidden")
    require(feasibility, 'PHASE32_PROTECTED_OUTCOME_READS_ALLOWED = False', "protected outcomes forbidden")
    require(feasibility, '"target_outcome_rows_read": 0', "zero target outcome reads")
    require(feasibility, '"protected_candidate_rows_read": 0', "zero protected candidate reads")
    require(feasibility, '"protected_return_rows_read": 0', "zero protected return reads")
    require(feasibility, '"phase33_signal_to_trade_entry_satisfied": False', "Phase33 remains blocked")
    require(feasibility, "_sample_rows", "deterministic bounded SEC sample")
    require(feasibility, "sec_filing_date_matches", "SEC/Massive filing-date reconciliation")
    require(feasibility, "item_codes_present", "structured SEC item-code coverage")

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

    # Frozen feasibility-era records retain the exact pre-freeze state.
    require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner hypothesis boundary")
    require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "runner outcome boundary")
    require(runner, "Broker/order/PAPER/LIVE activity: DISABLED", "runner trading boundary")
    require(runner, "SEC fair-access identity: ATLAS + local", "runner fair-access declaration")
    require(runner, "data.sec.gov company submissions metadata", "runner SEC source")
    require(runner, "item-code provenance only", "runner item-code boundary")
    require(incident, "SIXTH SOURCE-FORMAT FAILURE", "sixth source-format incident provenance")
    require(incident, "524", "target response diagnostic provenance")
    require(incident, "Submissions API", "official SEC source migration")

    # Living docs may advance beyond feasibility; require preserved Phase32 provenance and current authority.
    for doc_name, doc in (
        ("roadmap", roadmap),
        ("status", status),
        ("phase doc", phase_doc),
        ("README", readme),
    ):
        require(doc, "Phase32", f"{doc_name} Phase32 provenance")
        require(doc, "ACCEPTED_NEGATIVE", f"{doc_name} final Phase32 disposition")
        require(doc, "solvency_distress_short", f"{doc_name} finalist provenance")
        require(doc, "Phase33", f"{doc_name} downstream authority boundary")

    require(roadmap, "Accepted foundation through Phase32", "roadmap accepted foundation")
    require(roadmap, "Phase33 — Signal-to-Trade Construction", "shifted signal-to-trade")
    require(roadmap, "Phase39 — Controlled LIVE Activation", "shifted LIVE phase")
    require(status, "Phase32 remains closed", "current Phase32 closeout state")
    require(status, "Historical supported alpha remains 0", "current zero-support boundary")
    require(status, "Phase33 remains blocked", "current downstream authority boundary")
    require(phase_doc, EXPECTED_MASSIVE_ENDPOINT, "Phase32 source endpoint")
    require(phase_doc, "data.sec.gov/submissions", "official SEC submissions source")
    require(phase_doc, EXPECTED_PUBLIC_RULE, "Phase32 timing rule")
    require(phase_doc, EXPECTED_CONTRACT_VERSION, "Phase32 no-market-outcome feasibility contract")
    require(
        phase_doc,
        "zero target/protected outcomes during source qualification",
        "Phase32 source-qualification outcome blindness",
    )
    require(flow, "Accepted project foundation: **through Phase32**", "current flow foundation")
    require(flow, "Phase33", "current flow downstream boundary")
    require(readme, "Phase32 is `ACCEPTED_NEGATIVE`", "README final Phase32 state")
    require(readme, "Phase39", "README downstream numbering")
    require(workflow, "Validate Phase 32 SEC 8-K feasibility contracts", "CI Phase32 step")
    require(workflow, "python scripts/validate_phase32.py", "CI Phase32 validator command")
    if not (PROJECT_ROOT / "tests" / "unit" / "test_phase32_feasibility.py").is_file():
        raise AssertionError("Phase32 focused unit tests are missing")

    print("ATLAS Phase 32 SEC 8-K feasibility contracts: PASS")
    print(f"- source Phase31 merge is pinned: {EXPECTED_SOURCE_MERGE}")
    print("- feasibility v2 retains official data.sec.gov company submissions metadata")
    print("- exact accession, original 8-K form, filing date, acceptance time, and item codes remain pinned")
    print("- archived submissions lookup remains filing-date bounded and capped at two shards")
    print("- SEC requests retain declared identity, gzip/deflate, JSON, and one request/second")
    print("- frozen Phase32 source/feasibility artifacts retain exact official SEC source semantics while living status advances")
    print("- Phase33 signal-to-trade and all broker/order/PAPER/LIVE authority remain blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
