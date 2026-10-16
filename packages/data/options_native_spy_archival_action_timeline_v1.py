from __future__ import annotations

"""Bounded offline SPY corporate-action timeline across frozen DEVELOPMENT clocks.

Archived action events are *not* historical point-in-time announcement records.
This module indexes one accepted ledger only, after prior original-page equality
proof, without scanning prices or options or changing any accepted research.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import _action_symbols
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_action_source_proof_v1 import _project, _event_dates
from packages.data.options_native_stock_input_review_v1 import (
    MAX_ACTION_COMPRESSED, MAX_METADATA, _file, _gzip_records, _json,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-archival-action-timeline-v1"
START = date(2017, 11, 1)
END = date(2025, 12, 23)
MAX_REPORT_INPUT = 4 * 1024 * 1024
MAX_EVENT_CANDIDATES = 1024
MAX_LEDGER_RECORDS = 500000
MISSING_CLOCK = "2019-08-12T19:59:00+00:00"


class SpyArchivalTimelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PinnedSource:
    path: str
    sha256: str
    fingerprint: str


COVERAGE = PinnedSource(
    "data/research/options_native_spy_development_clock_coverage_v1/bf18bb1a4c7e38f0.json",
    "962852e3fc3739494b9758a8916ebe9ba0dfb8cdcadc71a651fa254e99455191",
    "bf18bb1a4c7e38f0dad91e1afaf3dd93d3dbdea9692f9e1345cf3b25efb56c2f",
)
ACTION_PROOF = PinnedSource(
    "data/research/options_native_spy_action_source_proof_v1/b0cbad9dca14d6ce.json",
    "3880427d8300d814cebd7ede1c6a2b6dc72c51d8a50fc686a75932081566b237",
    "b0cbad9dca14d6ce0221cd684473fbc3190e17248c42b0b0909c0854a9f8d929",
)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise SpyArchivalTimelineError(reason)


def _load_pinned(settings: AtlasSettings, pinned: PinnedSource) -> dict[str, Any]:
    path = settings.resolved_path(pinned.path)
    _require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_REPORT_INPUT,
             "pinned historical input report missing or oversized")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == pinned.sha256,
             "pinned report raw-byte identity mismatch")
    def bad_constant(_: str) -> None:
        raise SpyArchivalTimelineError("pinned report contains nonfinite JSON number")
    try:
        report = json.loads(raw, parse_constant=bad_constant)
    except (ValueError, UnicodeError) as exc:
        raise SpyArchivalTimelineError("malformed pinned report JSON") from exc
    _require(isinstance(report, dict)
             and report.get("report_fingerprint") == pinned.fingerprint
             and _fingerprint({k: v for k, v in report.items() if k != "report_fingerprint"})
             == pinned.fingerprint, "pinned report content fingerprint mismatch")
    return report


def verify_source_bindings(coverage: dict, proof: dict) -> None:
    expected_coverage = {
        "contract": "atlas-options-native-spy-development-minute-clock-coverage-v1",
        "status": "PHYSICAL_COVERAGE_REVIEW_ONLY_NO_PIT_INPUT_ACCEPTANCE",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "accepted_native_source_fingerprint": "6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664",
        "frozen_plan_fingerprint": "d6747846cc1395bcf6da9cbeef407e295190c2f9f3bac18eb1aacc4e376c8321",
        "target_weekly_cases": 411, "raw_complete_weekly_cases": 407,
        "raw_incomplete_weekly_cases": 4, "target_months": 97,
        "scanned_monthly_units": 97, "unique_exact_clocks_requested": 2407,
        "observed_exact_clocks": 2406, "unavailable_months": [],
        "historical_publication_and_adjustment_qualified": False,
        "raw_close_source_qualified_for_features": False,
        "pilot_input_acceptance": False, "forecast_total_variance": None,
        "economic_log_returns": None, "historical_option_premiums": None,
        "protected_return_rows_read": 0, "option_outcomes_read": 0,
    }
    expected_proof = {
        "contract": "atlas-options-native-spy-action-source-proof-v1",
        "status": "COMPLETE_SOURCE_RECONCILIATION_WITH_AVAILABILITY_GAPS",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "scanned_page_count": 379, "reconciled_action_records": 378362,
        "source_page_hashes_verified": True,
        "native_ledger_exactly_matches_original_pages": True,
        "historical_pit_publication_qualified": False,
        "action_effective_date_coverage_qualified": False,
        "economic_log_returns": None, "forecast_total_variance": None,
        "pilot_input_acceptance": False,
    }
    _require(all(coverage.get(k) == v for k, v in expected_coverage.items()),
             "frozen 411-case coverage report content changed")
    _require(all(proof.get(k) == v for k, v in expected_proof.items()),
             "original action archive proof content changed")
    _require(coverage.get("authority") == dict(AUTHORITY)
             and proof.get("authority") == dict(AUTHORITY) | {"raw_source_scans": 2},
             "historical reports gained authority")
    observations = coverage.get("observations")
    cases = coverage.get("cases")
    _require(isinstance(observations, dict) and len(observations) == 2407
             and isinstance(cases, list) and len(cases) == 411,
             "raw clock population changed")
    missing = [key for key, row in observations.items() if row.get("raw_close") is None]
    _require(missing == [MISSING_CLOCK], "single known physical gap changed")
    affected = ["2019-08-19", "2019-08-26", "2019-09-03", "2019-09-09"]
    _require([row.get("decision_date") for row in cases if row.get("missing_clocks")] == affected,
             "four dependent weekly abstentions changed")
    expected_keys = set()
    for case in cases:
        prior = case.get("prior_close_keys")
        _require(isinstance(prior, list) and len(prior) == 21 and len(set(prior)) == 21
                 and isinstance(case.get("spot_key"), str), "prior window or spot malformed")
        keys = [*prior, case["spot_key"]]
        _require(len(set(keys)) == 22, "weekly request duplicates a clock")
        expected_keys.update(keys)
        miss = [key for key in keys if observations.get(key, {}).get("raw_close") is None]
        _require(miss == case.get("missing_clocks")
                 and case.get("exact_minutes_present") == 22 - len(miss)
                 and case.get("historical_input_accepted") is False
                 and case.get("forecast_total_variance") is None,
                 "physical case does not agree with cached observations")
    _require(expected_keys == set(observations), "physical clock keys missing or extra")
    _require(proof.get("spy_action_candidates") and len(proof["spy_action_candidates"]) == 2,
             "earlier pinned 2020 action selection changed")


def projected_archival_events(
    records: list[dict[str, Any]], pages: list[dict[str, Any]], *,
    start: date = START, end: date = END,
) -> list[dict[str, Any]]:
    """Select SPY events, including unknown-date records, without claiming coverage."""
    candidates: list[dict[str, Any]] = []
    seen = set()
    for row in records:
        _require(isinstance(row, dict) and isinstance(row.get("payload"), dict)
                 and isinstance(row.get("action_type"), str)
                 and type(row.get("source_page_index")) is int
                 and 0 <= row["source_page_index"] < len(pages)
                 and type(row.get("source_record_index")) is int
                 and row["source_record_index"] >= 0, "malformed normalized action ordinal")
        ordinal = (row["action_type"], row["source_page_index"], row["source_record_index"])
        _require(ordinal not in seen, "duplicate source action ordinal")
        seen.add(ordinal)
        if "SPY" not in _action_symbols(row["payload"]):
            continue
        out = _project(row, pages[row["source_page_index"]]["sha256"], start, end)
        if out is not None:
            candidates.append(out)
            _require(len(candidates) <= MAX_EVENT_CANDIDATES,
                     "SPY archival population exceeds fixed selection bound")
    return candidates


def index_weekly_action_exposure(cases: list[dict], candidates: list[dict]) -> list[dict]:
    """A candidate exposure index, NOT a no-action proof or a feature adapter."""
    dated = []
    undated = []
    for i, action in enumerate(candidates):
        dates = _event_dates(action)
        if dates:
            dated.append((i, set(x.isoformat() for x in dates)))
        else:
            undated.append(i)
    indexed = []
    for case in cases:
        prior = case["prior_close_keys"]
        # The first close is the return baseline. Ex-date action candidates
        # attach to the 20 return END dates, never to the decision day or future.
        ends = {datetime.fromisoformat(key).date().isoformat() for key in prior[1:]}
        hits = [i for i, event_dates in dated if ends.intersection(event_dates)]
        indexed.append({
            "decision_date": case["decision_date"],
            "quote_query_fingerprint": case["quote_query_fingerprint"],
            "missing_raw_clocks": case["missing_clocks"],
            "physical_prior_and_spot_present": not case["missing_clocks"],
            "archived_dated_action_candidate_indices": hits,
            "archived_undated_action_candidate_indices": list(undated),
            "archival_zero_action_coverage_proved": False,
            "historical_publication_revisions_proved": False,
            "historical_economic_returns_accepted": False,
            "forecast_total_variance": None,
        })
    return indexed


def build_spy_archival_action_timeline(
    settings: AtlasSettings, *, coverage_binding: PinnedSource = COVERAGE,
    proof_binding: PinnedSource = ACTION_PROOF,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    coverage = _load_pinned(settings, coverage_binding)
    proof = _load_pinned(settings, proof_binding)
    verify_source_bindings(coverage, proof)
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    manifest, _ = _json(layout, layout.manifests / "corporate_actions.json",
                        proof["action_manifest_sha256"])
    pages = manifest.get("pages")
    _require(isinstance(pages, list) and len(pages) == 379
             and manifest.get("page_count") == 379
             and manifest.get("action_record_count") == proof["reconciled_action_records"],
             "original corporate action manifest/page population drifted")
    _require(all(isinstance(page, dict) and isinstance(page.get("sha256"), str)
                 and len(page["sha256"]) == 64 for page in pages),
             "invalid action-page SHA receipts")
    ledger = layout.corporate_actions / "native_actions.jsonl.gz"
    _require(Path(str(manifest["native_actions"]["path"])).absolute() == ledger.absolute()
             and manifest["native_actions"]["sha256"] == proof["native_actions_sha256"],
             "corporate action ledger path or digest drifted")
    _file(layout, ledger, MAX_ACTION_COMPRESSED, proof["native_actions_sha256"])
    if progress:
        progress("pinned 411-case minute coverage and 379-page action proof verified; streaming one native action ledger")
    # The original 379 pages and 378362 records have ALREADY been mutually
    # reconciled by the pinned proof. Do not reopen original source pages here.
    rows = []
    first_2019 = []
    count = 0
    try:
        for record in _gzip_records(ledger):
            count += 1
            _require(count <= MAX_LEDGER_RECORDS, "archival ledger record count unbounded")
            rows.append(record)
            if count % 50000 == 0 and progress:
                progress(f"archival native records reviewed {count}/{proof['reconciled_action_records']}")
    except (OSError, EOFError, ValueError, TypeError) as exc:
        raise SpyArchivalTimelineError("accepted native action ledger unreadable") from exc
    _require(count == proof["reconciled_action_records"], "original native action count changed")
    candidates = projected_archival_events(rows, pages)
    del rows
    early = [x for x in candidates if x in proof["spy_action_candidates"]]
    _require(len(early) == 2, "2019/2020 SPY page candidates do not reconcile to prior original proof")
    indexed = index_weekly_action_exposure(coverage["cases"], candidates)
    types = dict(sorted(Counter(x["action_type"] for x in candidates).items()))
    undated = sum(x["effective_date_state"] == "UNKNOWN_EFFECTIVE_DATE" for x in candidates)
    report = {
        "contract": CONTRACT,
        "status": "ARCHIVAL_SPY_ACTION_INDEX_ONLY_PIT_AND_COVERAGE_UNQUALIFIED",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "input_identities": {
            "development_clock_coverage_raw_sha256": coverage_binding.sha256,
            "development_clock_coverage_fingerprint": coverage_binding.fingerprint,
            "original_action_proof_raw_sha256": proof_binding.sha256,
            "original_action_proof_fingerprint": proof_binding.fingerprint,
            "native_action_ledger_sha256": proof["native_actions_sha256"],
            "original_page_proof_reused": proof["report_fingerprint"],
        },
        "action_selection_window": [START.isoformat(), END.isoformat()],
        "native_ledger_records_reconciled": count,
        "original_pages_reopened": 0,
        "action_candidates": candidates,
        "action_candidates_by_type": types,
        "archival_candidates_with_unknown_effective_date": undated,
        "weekly_case_action_index": indexed,
        "weekly_decisions": len(indexed),
        "physical_input_complete_weekly_decisions": coverage["raw_complete_weekly_cases"],
        "single_missing_minute": MISSING_CLOCK,
        "four_rejected_physical_weeks": [case["decision_date"] for case in coverage["cases"]
                                        if case["missing_clocks"]],
        "archival_date_absence_proves_no_actions": False,
        "complete_historical_action_coverage_qualified": False,
        "historical_asof_publication_revisions_qualified": False,
        "no_action_defaults_authorized": False,
        "historical_economic_return_adapter": False,
        "economic_log_returns": None,
        "forecast_total_variance": None,
        "option_inputs_accepted": False,
        "historical_performance_evidence": False,
        "pilot_input_acceptance": False,
        "source_scans": {"native_action_ledgers": 1, "original_action_pages": 0,
                         "daily_units": 0, "minute_units": 0, "option_histories": 0,
                         "outcomes": 0, "provider_requests": 0},
        "authority": dict(AUTHORITY),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
