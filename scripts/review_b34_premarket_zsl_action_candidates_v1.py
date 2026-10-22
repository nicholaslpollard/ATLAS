from __future__ import annotations

"""Offline April ZSL action candidates tied to an accepted premarket report.

Reuses a previously proved 379-page action archive and reads only its
hash-bound native ledger; never opens original pages, bars, trades or outcomes.
Historical split/identity/PIT completeness remains UNQUALIFIED.
"""

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings, load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.b34_premarket_zsl_action_candidates_v1 import (
    CONTRACT as PROJECTION_CONTRACT,
    EXPECTED_PAGES, EXPECTED_RECORDS, project_archived_candidates,
)
from packages.data.options_native_spy_archival_action_timeline_v1 import (
    ACTION_PROOF, _load_pinned,
)
from packages.data.options_native_stock_input_review_v1 import (
    MAX_ACTION_COMPRESSED, _file, _gzip_records, _json,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "atlas-b34-zsl-prior20-archival-action-source-check-v1"
SOURCE_REPORT = (
    "data/research/b34_premarket_context_v1/"
    "b34_premarket_prior20_volume_v1_f9f1817ce60a295d.json"
)
OUTPUT_ROOT = "data/research/b34_premarket_context_v1"
SOURCE_REPORT_PREFIX = "f9f1817ce60a295d"
MAX_SOURCE_REPORT = 512 * 1024
MAX_OUTPUT = 512 * 1024


def _fingerprint(report: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")
    ).hexdigest()


def _validate_prior20_receipt(report: dict[str, Any]) -> int:
    if not isinstance(report, dict) or any(
        report.get(k) != v for k, v in {
            "contract": "atlas-b34-premarket-prior20-source-review-v1",
            "source_contract": "atlas-b34-premarket-prior20-volume-observation-v1-no-signal",
            "status": "PRIOR20_SOURCE_DIAGNOSTIC_NO_SIGNAL",
            "symbol": "ZSL", "session_date": "2026-04-30",
            "selected_symbol": "ZSL", "selected_session": "2026-04-30",
            "prior_rows_read": 5150,
            "signal_authority": False,
            "split_or_corporate_action_history_checked": False,
            "provider_requests": 0, "broker_requests": 0,
            "protected_outcomes_opened": 0,
        }.items()
    ):
        raise ValueError("PRIOR20_RETAINED_SOURCE_SCOPE_CHANGED")
    expected_dates = [
        d.isoformat() for d in MarketCalendar().sessions_in_range(
            date(2026, 4, 1), date(2026, 4, 29)
        )
    ]
    if len(expected_dates) != 20 or report.get("prior_session_dates") != expected_dates:
        raise ValueError("PRIOR20_EXACT_EXCHANGE_SESSIONS_CHANGED")
    snapshots = report.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 3:
        raise ValueError("PRIOR20_CLOCK_POPULATION_CHANGED")
    for obs, (clock, volume, median) in zip(snapshots, [
        ("09:20:00", 708692, 1058953.5),
        ("09:30:00", 724192, 1092517.0),
        ("09:35:00", 724192, 1092517.0),
    ], strict=True):
        if obs.get("volume_ratio_admissible_as_strategy_input") is not False:
            raise ValueError("PRIOR20_GAINED_STRATEGY_AUTHORITY")
        if (obs.get("decision_clock_et") != clock
                or obs.get("current_observed_premarket_volume") != volume
                or obs.get("prior_20_median_observed_premarket_volume") != median
                or obs.get("prior_session_count") != 20
                or obs.get("prior_sessions_with_observed_premarket") != 20
                or obs.get("prior_sessions_missing_premarket") != []
                or not isinstance(obs.get("raw_volume_ratio_diagnostic_only"), (float, int))
                or not math.isclose(obs["raw_volume_ratio_diagnostic_only"],
                                    volume / median, abs_tol=1e-12, rel_tol=0)):
            raise ValueError("PRIOR20_OBSERVED_VOLUME_OR_CLOCK_DRIFT")
    return len(expected_dates)


def _load_prior20(settings: AtlasSettings) -> tuple[dict[str, Any], str]:
    path = settings.resolved_path(SOURCE_REPORT)
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= MAX_SOURCE_REPORT):
        raise ValueError("PINNED_PRIOR20_REPORT_UNAVAILABLE")
    raw = path.read_bytes()
    def reject_constant(_: str) -> None:
        raise ValueError("PINNED_PRIOR20_NONFINITE_JSON")
    report = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(report, dict):
        raise ValueError("PINNED_PRIOR20_NOT_OBJECT")
    expected = _fingerprint({k: v for k, v in report.items()
                             if k != "fingerprint"})
    if (not expected.startswith(SOURCE_REPORT_PREFIX)
            or report.get("fingerprint") != expected):
        raise ValueError("PINNED_PRIOR20_FINGERPRINT_DRIFT")
    _validate_prior20_receipt(report)
    return report, hashlib.sha256(raw).hexdigest()


def run_review(settings: AtlasSettings) -> dict[str, Any]:
    previous, prior_sha = _load_prior20(settings)
    proof = _load_pinned(settings, ACTION_PROOF)
    if (proof.get("source_page_hashes_verified") is not True
            or proof.get("native_ledger_exactly_matches_original_pages") is not True
            or proof.get("reconciled_action_records") != EXPECTED_RECORDS
            or proof.get("historical_pit_publication_qualified") is not False
            or proof.get("action_effective_date_coverage_qualified") is not False):
        raise ValueError("ORIGINAL_ARCHIVE_PROOF_NOT_ACCEPTED")
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    snapshot, _ = _json(layout, layout.manifests / "source_snapshot.json",
                        proof["source_snapshot_sha256"])
    manifest, _ = _json(layout, layout.manifests / "corporate_actions.json",
                        proof["action_manifest_sha256"])
    pages = manifest.get("pages")
    if (not isinstance(pages, list) or len(pages) != EXPECTED_PAGES
            or manifest.get("page_count") != EXPECTED_PAGES
            or manifest.get("action_record_count") != EXPECTED_RECORDS
            or manifest.get("native_actions") != snapshot.get("corporate_actions_native")
            or manifest.get("raw_bundle") != snapshot.get("corporate_actions_raw_bundle")
            or manifest.get("page_count") != snapshot.get("corporate_action_page_count")
            or manifest.get("action_record_count") != snapshot.get("corporate_action_record_count")):
        raise ValueError("ARCHIVAL_SOURCE_MANIFEST_CHANGED")
    page_hashes = [p.get("sha256") if isinstance(p, dict) else None for p in pages]
    ledger = layout.corporate_actions / "native_actions.jsonl.gz"
    if (Path(str(manifest["native_actions"].get("path"))).absolute()
            != ledger.absolute()
            or manifest["native_actions"].get("sha256")
            != proof["native_actions_sha256"]):
        raise ValueError("ARCHIVAL_NATIVE_LEDGER_SOURCE_CHANGED")
    _file(layout, ledger, MAX_ACTION_COMPRESSED, proof["native_actions_sha256"])

    candidates = project_archived_candidates(
        _gzip_records(ledger), page_hashes, expected_records=EXPECTED_RECORDS,
    )
    outcome = {
        **candidates,
        "contract": CONTRACT,
        "projection_contract": PROJECTION_CONTRACT,
        "status": "SOURCE_CANDIDATES_ONLY_NO_SPLIT_COMPARABILITY",
        "symbol": "ZSL",
        "review_window": ["2026-04-01", "2026-04-30"],
        "prior_20_report_raw_sha256": prior_sha,
        "prior_20_report_fingerprint": previous["fingerprint"],
        "prior_20_canonical_source_sha256": previous["source_canonical_sha256"],
        "accepted_original_action_proof_fingerprint": ACTION_PROOF.fingerprint,
        "native_action_ledger_sha256": proof["native_actions_sha256"],
        "action_manifest_sha256": proof["action_manifest_sha256"],
        "source_snapshot_sha256": proof["source_snapshot_sha256"],
        "archive_process_date_scope": [manifest.get("start"), manifest.get("cutoff")],
        "raw_source_reads": {
            "original_action_pages": 0, "native_action_ledgers": 1,
            "stock_minutes": 0, "option_histories": 0,
        },
        "note": (
            "Original archive is retrospective, known not to be complete "
            "for all issuers/events; recorded dates are not release clocks. "
            "Zero observed actions is NOT a certified no-action window."
        ),
    }
    outcome["report_fingerprint"] = _fingerprint(outcome)
    return outcome


def _save(settings: AtlasSettings, report: dict[str, Any]) -> Path:
    settings.assert_external_storage_binding("research_evidence")
    folder = settings.resolved_path(OUTPUT_ROOT)
    encoded = (json.dumps(report, sort_keys=True, indent=2,
                          allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_OUTPUT:
        raise ValueError("BOUNDED_ZSL_ACTION_REPORT_TOO_LARGE")
    filename = "b34_zsl_april_action_candidates_v1_" + report["report_fingerprint"][:16] + ".json"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    if path.is_symlink():
        raise ValueError("ACTION_OUTPUT_IS_SYMLINK")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("IMMUTABLE_ACTION_REPORT_COLLISION")
    else:
        with path.open("xb") as handle:
            handle.write(encoded)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS B34 ZSL APRIL ARCHIVAL ACTION CANDIDATES V1", flush=True)
    print("  Reuses pinned original archive; ZERO new provider/broker/outcome calls.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = run_review(settings)
        print(f"  prior20={report['prior_20_report_fingerprint'][:16]} "
              f"archive_rows={report['archive_records_checked']} "
              f"candidates={report['zsl_candidate_count']} "
              f"split_type={report['zsl_split_type_candidates']} "
              f"undated={report['zsl_undated_candidates']}", flush=True)
        for row in report["zsl_action_candidates"]:
            print(f"  action={row['action_type']} "
                  f"dates={row['recorded_event_dates']} "
                  f"ordinal={row['source_page_index']}/{row['source_record_index']}", flush=True)
        if not args.no_write:
            print("  retained_report=" + str(_save(settings, report)), flush=True)
        print("  COMPLETE status=SOURCE_CANDIDATES_ONLY_NO_SPLIT_COMPARABILITY "
              "signal_authority=False provider_requests=0 "
              "protected_outcomes_opened=0", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print("  STOP error_type=" + type(exc).__name__, flush=True)
        print("  Original sources preserved; no missing-action fallback or new data calls.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
